from abc import ABC, abstractmethod


class BaseAgent(ABC):
	name: str = "base"

	@abstractmethod
	def respond(self, message: str) -> str:
		"""Return a domain-specific guidance response for the incoming message."""

	@abstractmethod
	def suggested_next_step(self) -> str:
		"""Return the recommended next user action for this agent context."""
