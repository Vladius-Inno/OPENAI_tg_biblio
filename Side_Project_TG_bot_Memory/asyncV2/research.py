import pandas as pd
from openai.embeddings_utils import get_embedding, cosine_similarity
import openai
import os
from typing import List
from tenacity import retry, stop_after_attempt, wait_random_exponential
import time


@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
def get_embedding_delayed(text: str, engine="text-similarity-davinci-001") -> List[float]:
    # replace newlines, which can negatively affect performance.
    text = text.replace("\n", " ")
    time.sleep(1)
    return openai.Embedding.create(input=[text], engine=engine)["data"][0]["embedding"]


def read_embedding(file):
    df = pd.read_csv(file + '_embeddings.csv', dtype={'line': int, 'text': str,
                                                      'page': int, 'length': int,
                                                      'embeddings': object})
    df.embeddings = df.embeddings.apply(lambda x: [float(y) for y in
                                                   x.strip('[').strip(']').replace(' ', '').split(',')])
    return df


class Parser():

    def parse_txt(self, file):
        with open(file) as f:
            txt = f.readlines()
        print("Parsing txt")
        number_of_pages = len(txt) // 10
        print(f"Total number of pages: {number_of_pages}")
        paper_text = []
        counter = 0
        for line in txt:
            if line != '':
                counter += 1
                paper_text.append({
                    'line': counter,
                    'text': line.strip(),
                    'page': counter // 10 + 1
                })
        print("Done parsing paper")
        with open('txt_' + file, 'w') as f:
            f.write('\n'.join(str(x) for x in paper_text))
        return {'result': 'ok'}

    def make_df(self, file):
        print('Creating dataframe')
        with open('txt_' + file) as f:
            lines = f.readlines()
        text = []
        for el in lines:
            text.append(eval(el))
        filtered_pdf = []
        for row in text:
            if len(row['text']) < 5:
                continue
            filtered_pdf.append(row)
        df = pd.DataFrame(filtered_pdf)
        # remove elements with identical df[text] and df[page] values
        df = df.drop_duplicates(subset=['text', 'page'], keep='first')
        df['length'] = df['text'].apply(lambda x: len(x))
        df.to_csv(file + '_data.csv', index=False)
        print('Done creating dataframe')
        return {'result': 'ok'}

    def calculate_embeddings(self, file):
        df = pd.read_csv(file + '_data.csv')
        print('Calculating embeddings')
        embedding_model = "text-embedding-ada-002"
        openai.api_key = os.environ['API_KEY']
        try:
            embeddings = df.text.apply([lambda x: get_embedding_delayed(x, engine=embedding_model)])
            df["embeddings"] = embeddings
            df.to_csv(file + '_embeddings.csv', index=False)
            print('Done calculating embeddings')
        except Exception as e:
            print("Didn't calculate the embeddings", e)
        return {'result': 'ok'}

    def search_embeddings(self, df, query, n=3):
        openai.api_key = os.environ['API_KEY']
        embedding_model = "text-embedding-ada-002"
        try:
            query_embedding = get_embedding(
                query,
                engine=embedding_model
            )
            df["similarity"] = df.embeddings.apply(lambda x: cosine_similarity(x, query_embedding))
            results = df.sort_values("similarity", ascending=False, ignore_index=True)
            # make a dictionary of the first three results with the page number as the key and the text
            # as the value. The page number is a column in the dataframe.
            results = results.head(n)
        except Exception as e:
            print("Didn't manage to find embeddings", e)
            return None

        # sources = []
        # for i in range(n):
        #     # append the page number and the text as a dict to the sources list
        #     sources.append({'Page ' + str(results.iloc[i]['page']): results.iloc[i]['text'][:150] + '...'})
        # print(sources)
        return results.head(n)

    def create_prompt(self, df, file, user_input):
        result = self.search_embeddings(df, user_input, n=3)
        with open(file, 'r') as f:
            book_name = str(f.readline()).strip()
        prompt = """Ты языковая модель с экспертизой в анализе литературы и книг.
Тебе зададут вопрос и несколько текстовых эмбеддингов (embeddings) из книги """ + book_name + """
в порядке их косинусного сходства (cosine similarity) по отношению к запросу. 
Ты должна вернуть ответ на вопрос на основании этих данных.
      Вопрос: """ + user_input + """
      Эмбеддинги (embeddings): 
      1.""" + str(result.iloc[0]['text']) + """
      2.""" + str(result.iloc[1]['text']) + """
      3.""" + str(result.iloc[2]['text']) + """
Дай ответ на этот вопрос, основываясь на тексте книги."""
        print('Done creating prompt')
        print(prompt)
        return prompt

    def gpt(self, prompt):
        print('Sending request to GPT-3')
        openai.api_key = os.environ['API_KEY']
        try:
            r = openai.Completion.create(model="text-davinci-003", prompt=prompt, temperature=0.8, max_tokens=1500)
            answer = r.choices[0]['text']
            # response = {'answer': answer, 'sources': sources}
            response = answer.strip()
        except Exception as e:
            print("Didn't get response from GPT with embeddings", e)
            response = None
        print('Done sending request to GPT-3')
        return response


def process_book(file):
    if os.path.exists(file + '_embeddings.csv'):
        print('File with parsed text exists, no need for parsing')
        return {'result': 'had the book'}
    print("Processing txt")
    parser = Parser()
    _ = parser.parse_txt(file=file)
    _ = parser.make_df(file=file)
    _ = parser.calculate_embeddings(file=file)
    print("Done processing the book", file)
    return {'result': 'processed the book'}


def reply(file, query):
    if os.path.exists(file + '_embeddings.csv'):
        df = read_embedding(file=file)
        print('File with parsed text exists, no need for parsing')
    else:
        print('The new book, need to process')
        process_book(file)
        df = read_embedding(file=file)
    parser = Parser()
    query = str(query)
    prompt = parser.create_prompt(df, file, query)
    response = parser.gpt(prompt)
    print(response)
    return response


if __name__ == '__main__':

    book = 'ClockworkOrange.txt'
    query = 'Есть ли у Ктулху друзья?'
    reply(book, query)


