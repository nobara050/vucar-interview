from abc import ABC, abstractmethod
import config

# =============================================================================
# ======================== LLM CLIENT INTERFACE ===============================
# =============================================================================
class BaseLLM(ABC):

    @abstractmethod
    def generate(self, prompt: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate_with_tools(self, prompt: str, tools: list) -> dict:
        """
        Gọi LLM với tool definitions.
        Trả về:
        {
            "tool_calls": [{"tool": "...", "params": {...}}],
            "text": "..." (nếu LLM không gọi tool)
        }
        """
        raise NotImplementedError


# =============================================================================
# ==================== IMPLEMENTATION FOR GEMINI  =============================
# =============================================================================

class GeminiLLM(BaseLLM):

    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=config.LLM_API_KEY)
        self._genai = genai
        self._model_name = config.LLM_MODEL

    def generate(self, prompt: str) -> str:
        model = self._genai.GenerativeModel(self._model_name)
        response = model.generate_content(
            prompt,
            generation_config=self._genai.types.GenerationConfig(temperature=0.2)
        )
        return response.text.strip()

    def generate_with_tools(self, prompt: str, tools: list) -> dict:
        """
        Dùng Gemini native function calling.
        tools: list of genai.protos.FunctionDeclaration hoặc dict schema
        """
        model = self._genai.GenerativeModel(
            model_name=self._model_name,
            tools=tools
        )
        response = model.generate_content(
            prompt,
            generation_config=self._genai.types.GenerationConfig(temperature=0.1)
        )

        tool_calls = []
        text = ""

        for part in response.parts:
            # Part là function call
            if hasattr(part, "function_call") and part.function_call.name:
                fc = part.function_call
                tool_calls.append({
                    "tool": fc.name,
                    "params": dict(fc.args)
                })
            # Part là text
            elif hasattr(part, "text") and part.text:
                text += part.text

        return {
            "tool_calls": tool_calls,
            "text": text.strip()
        }

# ============================================================================
# =================== IMPLEMENTATION FOR OPENAI  =============================
# ============================================================================

class OpenAILLM(BaseLLM):

    def __init__(self):
        from openai import OpenAI
        self._client = OpenAI(api_key=config.LLM_API_KEY)

    def generate(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return response.choices[0].message.content.strip()

    def generate_with_tools(self, prompt: str, tools: list) -> dict:
        response = self._client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
            tool_choice="auto",
            temperature=0.1
        )
        message = response.choices[0].message
        tool_calls = []
        text = message.content or ""

        if message.tool_calls:
            import json
            for tc in message.tool_calls:
                tool_calls.append({
                    "tool": tc.function.name,
                    "params": json.loads(tc.function.arguments)
                })

        return {
            "tool_calls": tool_calls,
            "text": text.strip()
        }


# =============================================================================
# ====================== FACTORY FUNCTION =====================================
# =============================================================================

def get_llm_client() -> BaseLLM:
    providers = {
        "gemini": GeminiLLM,
        "openai": OpenAILLM,
    }
    provider_class = providers.get(config.LLM_PROVIDER)
    if not provider_class:
        raise ValueError(f"LLM provider không hợp lệ: {config.LLM_PROVIDER}. Chọn: gemini | openai")
    return provider_class()


llm_client = get_llm_client()
