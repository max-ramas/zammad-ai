from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler


class LangfuseClient:
    """Client for interacting with Langfuse to fetch prompts and build RunnableConfig with Langfuse callbacks."""

    def __init__(self) -> None:
        self.langfuse_handler: CallbackHandler = CallbackHandler()
        self.langfuse: Langfuse = Langfuse()  # Assumes Langfuse is configured via environment variables or other means

    def get_prompt(self, prompt_name: str, prompt_label: str = "production") -> str:
        """Fetch a prompt template from Langfuse by name and label.

        Args:
            prompt_name (str): The name of the prompt to fetch.
            prompt_label (str): The label of the prompt to fetch (default: "production").
        Returns:
            str: The text of the fetched prompt template.
        """
        return self.langfuse.get_prompt(prompt_name, label=prompt_label).prompt

    def build_config(self, session_id: str | None = None) -> RunnableConfig:
        """Build a RunnableConfig with Langfuse callback handler and session metadata.

        Args:
            session_id (str | None, optional): The session ID to use for Langfuse tracking. If None, a new session ID will be generated. Defaults to None.

        Returns:
            RunnableConfig: A RunnableConfig configured with Langfuse callbacks and session metadata.
        """
        if session_id is None:
            session_id = self.generate_session_id()

        return RunnableConfig(
            callbacks=[self.langfuse_handler],
            metadata={
                "langfuse_session_id": session_id,
            },
        )

    def generate_session_id(self) -> str:
        """
        Generate a new unique session ID for Langfuse tracing.

        Returns:
            str: A unique session ID.
        """
        return str(uuid4())
