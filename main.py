from openai import OpenAI
import requests
from pathlib import Path
import time
import json
from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env.

client = OpenAI(
    # Defaults to os.environ.get("OPENAI_API_KEY")
)

class NelsonBot:
    ticker="SAVE"
    assistant_id="asst_3fLJ8tW1zJH92JGAQpHKV8Or"
    news_thread=None
    news_thread_id=None
    sec_thread=None
    sec_thread_id=None
    # override_sec_thread_id="thread_5eM727bMvzJ16qA06oGgbzEn" # 2 10Q, may be to big
    override_sec_thread_id="thread_aYiwyNiE1MqsYJq2KtwZZsJ7" # only one 10Q
    override_news_thread_id="thread_oGhToCj0zDE9HNtUAmXGmaaq"

    def __init__(self):
        self.data = []

        self.input_ticker()

    def sec_init(self):
        headers = {'User-Agent': 'CPL nlai@chinesepowered.com'}

        # get list of files
        print("Getting list of SEC filings from OpenBB")
        r = requests.get("https://mindsdb2024.openbb.dev/api/v1/equity/fundamental/filings?provider=sec&symbol="+self.ticker+"&limit=500", auth=('openbb', 'mindsdb2024'))
        result_obj=r.json()
        results=result_obj["results"]

        reports=list()
        for result in results:
            if result.get("report_type")=="10-Q":
                reports.append(result)

        # create thread
        self.sec_thread = thread=client.beta.threads.create()
        self.sec_thread_id = self.sec_thread.id
        print("Created thread")
        print(thread)

        # sort reports by most recent
        reports.sort(key=lambda x: x.get("report_date"), reverse=True)

        print("Transloading filings from SEC to OpenAI")
        files_list=list() # list of file objects
        file_ids=list() # list of file IDs as strings
        for i,report in enumerate(reports):
            if i>1:
                break
            # download report to local as HTML
            filename=self.ticker+"-"+report.get("report_date")+"-"+report.get("report_type")+".html"
            files_list.append(filename)
            r = requests.get(report.get("report_url"),headers=headers)
            with open(filename, mode="w", encoding="utf-8") as file:
                file.write("10-Q file \n"+r.text)

            # upload file to OpenAI
            file_create_result=client.files.create(
                file=Path(filename),
                purpose="assistants",
            )
            print(file_create_result.id + " - "+ filename)
            file_ids.append(file_create_result.id)
            time.sleep(1)

        # associate files to thread via message
        print("Bot processing SEC filings")
        message=client.beta.threads.messages.create(thread_id=thread.id,role="user",content="These are the quarterly 10-Q SEC regulatory filings by date for stock ticker "+self.ticker,file_ids=file_ids)
        client.beta.threads.runs.create(assistant_id=self.assistant_id,thread_id=thread.id)

    def news_init(self):
        filename=self.ticker+".json"

        # get list of files
        print("Downloading news from OpenBB")
        r = requests.get("https://mindsdb2024.openbb.dev/api/v1/news/company?provider=benzinga&symbols="+self.ticker+"&display=full&start_date=2023-07-01&end_date=2024-01-26&limit=1000", auth=('openbb', 'mindsdb2024'))
        result_obj=r.json()
        results=result_obj["results"]

        with open(filename, mode="w") as file:
            file.write(json.dumps(results))

        # upload file to OpenAI
        print("Uploading news to OpenAI")
        file_create_result=client.files.create(
            file=Path(filename),
            purpose="assistants",
        )
        print(file_create_result.id + " - "+ filename)

        # create thread
        self.news_thread = thread = client.beta.threads.create()
        self.news_thread_id = self.news_thread.id
        print("Created thread")
        print(thread)

        # associate files to thread via message
        print("Bot processing news")
        message=client.beta.threads.messages.create(thread_id=thread.id,role="user",content="These are recent news articles related to stock ticker "+self.ticker+". The 'date' field has the article publish date, the 'title' field has the article title, and the 'text' field has a snippet of the article contents",file_ids=[file_create_result.id])
        client.beta.threads.runs.create(assistant_id=self.assistant_id,thread_id=thread.id)

    def input_ticker(self):
        print("===What ticker do you want to access?===")
        input_string=input()
        self.ticker=input_string

        self.post_ticker_init() # upload documents if needed
        self.main_menu()

    def post_ticker_init(self):
        # check cache if applicable

        #init news
        if self.ticker=="SAVE":
            self.news_thread_id="thread_oGhToCj0zDE9HNtUAmXGmaaq"
        else:
            self.news_init()
        #init sec
        if self.ticker=="SAVE" and self.override_sec_thread_id:
            #self.sec_thread_id="thread_aYiwyNiE1MqsYJq2KtwZZsJ7" # one 10Q, may not be init yet
            self.sec_thread_id="thread_5eM727bMvzJ16qA06oGgbzEn" # two 10Q
        else:
            self.sec_init()


    def main_menu(self):
        print("===Which Bot?===")
        print("1) News Bot")
        print("2) SEC Bot")
        print("3) Financials Bot")
        input_string=input()
        match input_string:
            case "1":
                self.input_news()
            case "2":
                self.input_sec()
            case "3":
                self.input_news()
            case _:
                print("Thanks for using NelsonBot")

    def input_news(self):
        print("===What do you want to ask news bot?===")
        input_string=input()
        # send to openai
        client.beta.threads.messages.create(thread_id=self.news_thread_id,role="user",content=input_string)
        run=client.beta.threads.runs.create(assistant_id=self.assistant_id,thread_id=self.news_thread_id)
        messages = self.poll_for_finish(self.news_thread_id,run.id) # wait for finish
        self.print_non_user_messages(messages)

        # go back to main menu
        self.main_menu()

    def input_sec(self):
        print("===What do you want to ask sec bot?===")
        input_string=input()
        # send to openai
        client.beta.threads.messages.create(thread_id=self.sec_thread_id,role="user",content=input_string)
        run=client.beta.threads.runs.create(assistant_id=self.assistant_id,thread_id=self.sec_thread_id)
        messages = self.poll_for_finish(self.sec_thread_id,run.id) # wait for finish
        self.print_non_user_messages(messages)

        # go back to main menu
        self.main_menu()


    def ask_initial_news(self):
        message=client.beta.threads.messages.create(thread_id=self.news_thread_id,role="user",content="What is the general sentiment of the latest news and why?")
        run=client.beta.threads.runs.create(assistant_id=self.assistant_id,thread_id=self.news_thread_id)


    def print_non_user_messages(self, messages):
        message_arr=list()
        for message in messages:
            if message.role=="user":
                break
            result=message.content[0].text.value
            message_arr.append(result)
        message_arr.reverse()
        for msg in message_arr:
            print(msg)

    def poll_for_finish(self,thread_id,run_id):
        while (True):
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )

            if run_status.status == 'completed':
                return client.beta.threads.messages.list(
                    thread_id=thread_id
                ) 
            elif run_status.status in ['queued', 'in_progress']:
                print("Still waiting for run to finish")
                time.sleep(1)
            else:
                print(f"Run status: {run_status.status}")
                break


bot = NelsonBot()
