# -*- coding: utf-8 -*-

from retrying_async import retry
import anthropic
import os
from constants import LITERATURE_EXPERT_ROLE, MODEL_CLAUDE, LIT_PROMPT, API_KEY

client = anthropic.AsyncAnthropic(
    # This is the default and can be omitted
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)


# Make the request to the OpenAI API
@retry(delay=3, attempts=3)
async def claude_ai(prompt, max_tokens, messages, gpt_role):
    # the example
    # messages = [
    #     {"role": "system", "content": "You are a helpful assistant."},
    #     {"role": "user", "content": "Who won the world series in 2020?"},
    #     {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
    #     {"role": "user", "content": "Where was it played?"}
    # ]
    if messages is None:
        messages = []

    answer = None

    if gpt_role == LITERATURE_EXPERT_ROLE:
        messages.append({"role": "system", "content": LIT_PROMPT})

    messages.append({"role": "user", "content": prompt})
    print("Claude sending request", messages)
    try:
        answer = await client.messages.create(
            model=MODEL_CLAUDE,
            max_tokens=max_tokens,
            messages=messages,
        )
    except Exception as e:
        print('Claude request failed', e)
    if answer:
        answer = answer.model_dump()
    print("The response:", answer)

    return answer['content'][0]['text']


claude_ai('Какие книги Стругацких можно рекомендовать любителям "мрачной" фантастики?', 1024, None)
