class GemmaClient:
    def __init__(self, model_name: str = "gemma"):
        self.model_name = model_name

    def generate(self, prompt: str) -> str:
        return f"Generated response for prompt: {prompt}"
