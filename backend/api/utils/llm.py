from groq import Groq
from backend.api.config.get_env import GROQ_API_KEY

client = Groq(
    api_key=GROQ_API_KEY
)

def generate_answer(query: str, context: str):

    response = client.chat.completions.create(

        model="openai/gpt-oss-120b",
        messages=[
                        {
                            "role": "system",
                            "content": """
            You are a medical evidence assistant.
            Answer only using the provided sources.
            For every important factual claim, cite the supporting source
            using exactly this format:
            [SOURCE_1]
            [SOURCE_2]
            Do not invent source IDs.
            If the sources are insufficient, say so.
            """
                        },
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
    return response.choices[0].message.content


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