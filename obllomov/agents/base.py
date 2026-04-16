from typing import *

from colorama import Fore
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.callbacks import BaseCallbackHandler
from pydantic import BaseModel

from obllomov.shared.log import logger

T = TypeVar("T", bound=BaseModel)

class LogCallbackHandler(BaseCallbackHandler):
    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> Any:
        formatted_prompts = "\n".join(prompts)
        _log.info(f"Prompt:\n{formatted_prompts}")
class BaseAgent:
    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def _raw_plan(
        self,
        prompt_template: str,
        input_variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        prompt = PromptTemplate.from_template(prompt_template)
        chain = prompt | self.llm | StrOutputParser()
        response = chain.invoke(input_variables)
        self._log(response)
        return response

    def _structured_plan(
        self,
        schema: type[T],
        prompt_template: str,
        input_variables: Optional[Dict[str, Any]] = None,
    ) -> T:
        prompt = PromptTemplate.from_template(prompt_template)
        chain = prompt | self.llm.with_structured_output(schema)

        response = chain.invoke(input_variables)


        self._log(response.model_dump_json(indent=2), request=prompt.format(**input_variables))
        return response

    def _log(self, response, prefix: str | None = None, request: str | None = None):
        if prefix is None:
            prefix = f"AI:"
        if request is not None:
            logger.info(f"{Fore.GREEN}USER:\n{request}{Fore.RESET}")
        logger.info(f"{Fore.GREEN}{prefix}\n{response}{Fore.RESET}")
