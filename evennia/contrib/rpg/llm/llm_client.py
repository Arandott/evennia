"""
LLM (Large Language Model) client, for communicating with an LLM backend. This can be used
for generating texts for AI npcs, or for fine-tuning the LLM on a given prompt.

Note that running a LLM locally requires a lot of power, and ideally a powerful GPU. Testing
this with CPU mode on a beefy laptop, still takes some 4s just on a very small model.

The server defaults to output suitable for a local server
https://github.com/oobabooga/text-generation-webui, but could be used for other LLM servers too.
It now also supports OpenAI-compatible APIs (OpenAI, DeepSeek, etc.).

See the LLM instructions on that page for how to set up the server. You'll also need
a model file - there are thousands to try out on https://huggingface.co/models (you want Text
Generation models specifically).

# Optional Evennia settings (if not given, these defaults are used)

DEFAULT_LLM_HOST = "http://localhost:5000"
DEFAULT_LLM_PATH = "/api/v1/generate"
DEFAULT_LLM_HEADERS = {"Content-Type": "application/json"}
DEFAULT_LLM_PROMPT_KEYNAME = "prompt"
DEFAULT_LLM_REQUEST_BODY = {...}   # see below, this controls how to prompt the LLM server.
DEFAULT_LLM_API_TYPE = ""  # or "openai" for OpenAI-compatible APIs

# For OpenAI-compatible APIs:
DEFAULT_LLM_API_KEY = ""  # Your API key
DEFAULT_LLM_MODEL = "gpt-3.5-turbo"  # Model name for OpenAI APIs

"""

import json

from django.conf import settings
from twisted.internet import defer, protocol, reactor
from twisted.internet.defer import inlineCallbacks
from twisted.web.client import Agent, HTTPConnectionPool, _HTTP11ClientFactory
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from zope.interface import implementer

from evennia import logger
from evennia.utils.utils import make_iter

DEFAULT_LLM_HOST = "http://127.0.0.1:5000"
DEFAULT_LLM_PATH = "/api/v1/generate"
DEFAULT_LLM_HEADERS = {"Content-Type": ["application/json"]}
DEFAULT_LLM_PROMPT_KEYNAME = "prompt"
DEFAULT_LLM_API_TYPE = ""  # or "openai"
DEFAULT_LLM_API_KEY = ""
DEFAULT_LLM_MODEL = "deepseek-chat"
DEFAULT_LLM_REQUEST_BODY = {
    "max_new_tokens": 250,  # max number of tokens to generate
    "temperature": 0.7,  # higher = more random, lower = more predictable
}

# OpenAI API defaults
OPENAI_DEFAULT_HOST = "https://api.openai.com"
OPENAI_DEFAULT_PATH = "/v1/chat/completions"
OPENAI_DEFAULT_REQUEST_BODY = {
    "model": "gpt-3.5-turbo",
    "temperature": 0.7,
    "max_tokens": 250,
}

# DeepSeek API defaults (as an example of OpenAI-compatible API)
DEEPSEEK_DEFAULT_HOST = "https://api.deepseek.com"
DEEPSEEK_DEFAULT_PATH = "/v1/chat/completions"

@implementer(IBodyProducer)
class StringProducer:
    """
    Used for feeding a request body to the HTTP client.
    """

    def __init__(self, body):
        self.body = bytes(body, "utf-8")
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class SimpleResponseReceiver(protocol.Protocol):
    """
    Used for pulling the response body out of an HTTP response.
    """

    def __init__(self, status_code, d):
        self.status_code = status_code
        self.buf = b""
        self.d = d

    def dataReceived(self, data):
        self.buf += data

    def connectionLost(self, reason=protocol.connectionDone):
        self.d.callback((self.status_code, self.buf))


class QuietHTTP11ClientFactory(_HTTP11ClientFactory):
    """
    Silences the obnoxious factory start/stop messages in the default client.
    """

    noisy = False


class LLMClient:
    """
    A client for communicating with an LLM server.
    Supports both local text-generation-webui and OpenAI-compatible APIs.
    """

    def __init__(self, on_bad_request=None):
        self._conn_pool = HTTPConnectionPool(reactor)
        self._conn_pool._factory = QuietHTTP11ClientFactory

        self.api_type = getattr(settings, "LLM_API_TYPE", DEFAULT_LLM_API_TYPE).lower()
        self.api_key = getattr(settings, "LLM_API_KEY", DEFAULT_LLM_API_KEY)
        self.model = getattr(settings, "LLM_MODEL", DEFAULT_LLM_MODEL)
        
        # Set defaults based on API type
        if self.api_type == "openai":
            self.hostname = getattr(settings, "LLM_HOST", OPENAI_DEFAULT_HOST)
            self.pathname = getattr(settings, "LLM_PATH", OPENAI_DEFAULT_PATH)
            self.request_body = getattr(settings, "LLM_REQUEST_BODY", OPENAI_DEFAULT_REQUEST_BODY)
            # Add Authorization header for OpenAI
            headers = getattr(settings, "LLM_HEADERS", DEFAULT_LLM_HEADERS).copy()
            if self.api_key:
                headers["Authorization"] = [f"Bearer {self.api_key}"]
            self.headers = headers
        else:
            # Default to local text-generation-webui format
            self.hostname = getattr(settings, "LLM_HOST", DEFAULT_LLM_HOST)
            self.pathname = getattr(settings, "LLM_PATH", DEFAULT_LLM_PATH)
            self.headers = getattr(settings, "LLM_HEADERS", DEFAULT_LLM_HEADERS)
            self.request_body = getattr(settings, "LLM_REQUEST_BODY", DEFAULT_LLM_REQUEST_BODY)
            
        self.prompt_keyname = getattr(settings, "LLM_PROMPT_KEYNAME", DEFAULT_LLM_PROMPT_KEYNAME)
        self.agent = Agent(reactor, pool=self._conn_pool)

    def _format_request_body_openai(self, prompt):
        """Structure the request body for OpenAI-compatible APIs"""
        request_body = self.request_body.copy()
        
        # Convert prompt to OpenAI messages format
        prompt = "\n".join(make_iter(prompt))
        
        request_body["messages"] = [
            {"role": "user", "content": prompt}
        ]
        
        # Ensure model is set
        if "model" not in request_body:
            request_body["model"] = self.model
            
        return request_body

    def _format_request_body_local(self, prompt):
        """Structure the request body for local text-generation-webui"""
        request_body = self.request_body.copy()
        prompt = "\n".join(make_iter(prompt))
        request_body[self.prompt_keyname] = prompt
        return request_body

    def _format_request_body(self, prompt):
        """Structure the request body for the LLM server"""
        if self.api_type == "openai":
            return self._format_request_body_openai(prompt)
        else:
            return self._format_request_body_local(prompt)

    def _handle_llm_response_body(self, response):
        """Get the response body from the response"""
        d = defer.Deferred()
        response.deliverBody(SimpleResponseReceiver(response.code, d))
        return d

    def _handle_llm_error(self, failure):
        """Correctly handle server connection errors"""
        failure.trap(Exception)
        return (500, failure.getErrorMessage())

    def _get_response_from_llm_server(self, prompt):
        """Call the LLM server and handle the response/failure"""
        request_body = self._format_request_body(prompt)

        if settings.DEBUG:
            logger.log_info(f"LLM request body: {request_body}")

        d = self.agent.request(
            b"POST",
            bytes(self.hostname + self.pathname, "utf-8"),
            headers=Headers(self.headers),
            bodyProducer=StringProducer(json.dumps(request_body)),
        )

        d.addCallbacks(self._handle_llm_response_body, self._handle_llm_error)
        return d

    def _extract_response_text_openai(self, response_data):
        """Extract text from OpenAI-compatible API response"""
        try:
            return response_data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            logger.log_err(f"Failed to parse OpenAI response: {e}, Response: {response_data}")
            return ""

    def _extract_response_text_local(self, response_data):
        """Extract text from local text-generation-webui response"""
        try:
            return response_data["results"][0]["text"]
        except (KeyError, IndexError) as e:
            logger.log_err(f"Failed to parse local LLM response: {e}, Response: {response_data}")
            return ""

    def _extract_response_text(self, response_data):
        """Extract response text based on API type"""
        if self.api_type == "openai":
            return self._extract_response_text_openai(response_data)
        else:
            return self._extract_response_text_local(response_data)

    @inlineCallbacks
    def get_response(self, prompt):
        """
        Get a response from the LLM server for the given npc.

        Args:
            prompt (str or list): The prompt to send to the LLM server. If a list,
                this is assumed to be the chat history so far, and will be added to the
                prompt in a way suitable for the api.

        Returns:
            str: The generated text response. Will return an empty string
                if there is an issue with the server, in which case the
                the caller is expected to handle this gracefully.

        """
        status_code, response = yield self._get_response_from_llm_server(prompt)
        if status_code == 200:
            if settings.DEBUG:
                logger.log_info(f"LLM response: {response}")
            try:
                response_data = json.loads(response)
                return self._extract_response_text(response_data)
            except json.JSONDecodeError as e:
                logger.log_err(f"Failed to parse LLM response JSON: {e}")
                return ""
        else:
            logger.log_err(f"LLM API error (status {status_code}): {response}")
            return ""
