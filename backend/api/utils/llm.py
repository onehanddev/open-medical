from groq import Groq, AsyncGroq
from config.get_env import GROQ_API_KEY
from opentelemetry import trace
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from api.schema.ask import ChatHistory


SYSTEM_PROMPT = {
                                "role": "system",
                                "content": """
                You are a medical evidence assistant.
                You must only talk about the topics related to medicine, pharmacy, health and the likes.
                Answer only using the provided sources.
                For every important factual claim, cite the supporting source
                using exactly this format:
                [SOURCE_1]
                [SOURCE_2]
                Do not invent source IDs.
                If the sources are insufficient, say so.

                Format your response as clean Markdown optimized for readability.

                Formatting rules:
                - Use ## for major sections.
                - Use ### for subsections.
                - Use bullet points for lists.
                - Use numbered lists for sequential steps.
                - Use **bold** for important medical terms.
                - Use Markdown tables when comparing multiple items.
                - Keep paragraphs short and readable.
                - Do not use unnecessary headings.
                - Do not wrap the entire response in a Markdown code block.
                """
                            }

MODEL_NAME = "openai/gpt-oss-120b"

tracer = trace.get_tracer(__name__)

client = AsyncGroq(
    api_key=GROQ_API_KEY
)

async def generate_answer(query: str, history: list[ChatHistory], context: str):

    with tracer.start_as_current_span("llm.generate_answer") as span:
        span.set_attribute("gen_ai.operation.name", "ask")
        span.set_attribute("gen_ai.request.model", MODEL_NAME)

        history_messages = [message.model_dump() for message in history]

        response = await client.chat.completions.create(
            stream=True,
            model=MODEL_NAME,
            messages=[
                SYSTEM_PROMPT,
                *history_messages,
                {
                    "role": "user",
                    "content": f"""
                    Question:
                    {query}
                    Sources:
                    {context}
                    """
                }
            ]
                    )
        print('========= resspoonsse', response)
        async for chunk in response:
            stream = chunk.choices[0].delta.content
            print('chat streaming chunk', stream)
            if stream:
                yield stream



def build_context(chunks):
    context_parts = []

    for idx, chunk in enumerate(chunks, start=1):
        context_parts.append(

            f"""

        SOURCE_{idx}    
            
        Page: {chunk.page_num}

        Chapter: {chunk.chapter}

        Section: {chunk.section}

        {chunk.content}

        """)
    return "\n\n---\n\n".join(context_parts)