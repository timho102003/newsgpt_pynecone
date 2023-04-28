import json
import requests
import feedparser
from typing import List
import pynecone as pc
from pygooglenews import GoogleNews
from newspaper import Article, Config
import nltk
import time
nltk.download('punkt')


class State(pc.State):
    text: str = ""
    titles: List[List] = []
    img_src: str = ""
    resource_href: List = []
    src_meta: List[List] = []
    summary: str = ""
    summary_end: bool = False
    summary_start: bool = False
    middle_summary_state:str = ""
    openai_key_show: bool = False
    _valid_state = ["info", "error", "success"]
    is_valid_code: str = _valid_state[0]
    _engine = GoogleNews(lang="en", country="US")
    _USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
    _article_config = Config()
    _article_config.request_timeout = 10
    # _article_config.follow_meta_refresh=True
    _article_config.browser_user_agent = _USER_AGENT
    _prompt = '''
            Please help me gather data from various media sources above and analyze it across multiple articles to recognize similarities and differences. 
            For instance, if several articles report on the launch of a new Tesla car, one source might state the retail price as $10, while another mentions it as $15. 
            The similarities between the articles would be that they all cover the new car launch, while the differences would be the varying retail prices reported. 
            The final output should include a summary paragraph followed by a list of similarities and differences, 
            where the differences are presented in the format of source A reporting a price of $10, while source B reports a price of $15.
            response should be formed organized and neat in html layout, give me the h3 title and highlight the keyword as bold.
        '''

    show_progress = False
    tmp_openai_key_text = ""
    OPENAI_API_KEY = ""  # os.environ["my_openai_key"]
    _ENDPOINT_URL = 'https://api.openai.com/v1/chat/completions'
    _OPENAI_HEADER: dict = {}

    def reset_state_and_go_home(self):
        # Reset state variables to their initial values
        self.titles = []
        self.img_src = ""
        self.resource_href = []
        self.src_meta = []
        self.summary = ""
        self.middle_summary_state = ""
        self.summary_start = False
        self.summary_end = False
        # Navigate to the home page
        return pc.redirect("/")

    def search(self):
        self.summary = ""
        self.middle_summary_state = ""
        self.titles = []
        self.src_meta = []
        self.summary_start = False
        self.summary_end = False
        if self.text != "intext:":
            src_response = self._engine.search(self.text, when="1d")
            # title, src, date, url
            for t in src_response["entries"]:
                self.titles.append(t["title"].split(" - ")[0])
                self.src_meta.append(
                    [t["source"]["title"], t["published"], t["link"]])

    def set_text(self, text):
        self.text = f"intext:{text}"

    def set_openai_key_text(self, text):
        self.tmp_openai_key_text = text

    def submit_openai_key(self):
        # Define the API endpoint URL
        endpoint_url = "https://api.openai.com/v1/models"

        # Set the headers for the API request
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.tmp_openai_key_text}"
        }
        # Send the API request
        response = requests.get(endpoint_url, headers=headers)

        self.is_valid_code = self._valid_state[int(
            response.status_code == 200) + 1]

        if self.is_valid_code == "success":
            self.OPENAI_API_KEY = self.tmp_openai_key_text
            self._OPENAI_HEADER = {"Content-Type": "application/json",
                                   "Authorization": f"Bearer {self.OPENAI_API_KEY}"
                                   }

    async def summarize(self, cur_title):
        self.summary_start = True
        cur_index = self.titles.index(cur_title)
        cur_src_meta = self.fetch_info(self.src_meta[cur_index][2])
        print(self.is_valid_code)
        print(cur_src_meta)
        self.middle_summary_state += "<strong>Start related content ........</strong>\n"
        if isinstance(cur_src_meta, dict) and self.is_valid_code == "success":
            self.img_src = cur_src_meta["image"]
            print("1")
            self.middle_summary_state += "<strong>{}</strong>\n".format(f"Processing Main Article: {cur_src_meta['title']}")
            print("2")
            related = self._engine.search(cur_src_meta['title'], when="3d")
            # print("----------- Finish finding related news")
            summary_list = [cur_src_meta["body"]]
            print("3")
            self.resource_href.append(cur_src_meta["url"])
            print("4")
            r_i = 1
            for r in related["entries"][1:6]:
                print(f"+++++++++++++: {r['title']}")
                r_meta = self.fetch_info(r["link"])
                if isinstance(r_meta, dict):
                    summary_list.append(r_meta["body"])
                    self.resource_href.append(r_meta["url"])
                    print(f"-------------: {r['title']}")
                    self.middle_summary_state += "<strong>{}</strong>\n".format(f"Processing Related Article {r_i}: {r['title']}")
                    r_i += 1
                    time.sleep(3)

            # self.summary = "\n".join(summary_list)
            self.call_openai(summary_list)
            # print("SUMMARY: ")
            # print(self.summary)
        elif isinstance(cur_src_meta, dict) and self.is_valid_code != "success":
            self.middle_summary_state = "<strong>Please set up your openai api-key before running NewsGPT</strong>"
        else:
            self.middle_summary_state = f"<strong>Something went wrong: {cur_src_meta}</strong>"
        self.summary = self.middle_summary_state
        self.summary_end = True
        print("Final Summary: ")
        print(self.middle_summary_state)

    def redirect(self):
        return pc.redirect("/")

    def fetch_info(self, rss_feed):
        news_feed = feedparser.parse(rss_feed)
        article = Article(news_feed["href"])  # , config=self._article_config)
        try:
            article.download()
            article.parse()
            article.nlp()
            return \
                {
                    "title": article.title,
                    "body": article.text,
                    "summary": article.summary,
                    "image": article.top_image,
                    "authors": article.authors,
                    "keywords": article.keywords,
                    "url": article.url
                }
        except Exception as e:
            return str(e)

    def call_openai(self, article_list):
        summary_list = []
        error_list = []
        # print("All Articles:")
        # print(". ".join(article_list))
        s_i = 1
        for idx, r in enumerate(article_list):
            messages = [
                {"role": "system", "content": "You are a very professional news artlce summization and analysis agent."},
                {"role": "user", "content": r + " " + "summarize the article above and preserve information on \
                                                           the following concepts: Personnel/Human Resources, Time and Place, Object/Thing. "},
            ]

            data = {
                "model": "gpt-3.5-turbo",
                "messages": messages,
                "temperature": 0.7
            }

            try:
                response = requests.post(
                    url=self._ENDPOINT_URL, headers=self._OPENAI_HEADER, data=json.dumps(data))
                response_json = response.json()
                print(response_json)
                answer = response_json["choices"][0]["message"]["content"].strip(
                )
                summary_list.append(answer)
                error_list.append("")
                self.middle_summary_state += "<strong>{}</strong>".format(f"Summarizing Article {s_i} ......")
            except Exception as e:
                error_list.append(e)

        if len(summary_list):
            summary_ = ", ".join([f"article {si} summary: {s}" for si, s in enumerate(
                summary_list)]) + self._prompt
            messages = [
                {"role": "system", "content": "You are a very professional news artlce summization and analysis agent."},
                {"role": "user", "content": summary_},
            ]

            data = {
                "model": "gpt-3.5-turbo",
                "messages": messages,
                "temperature": 0.7
            }
            print(messages)
            self.middle_summary_state += "<strong>{}</strong>".format(f"Analyzing All Articles .....")
            try:
                response = requests.post(
                    url=self._ENDPOINT_URL, headers=self._OPENAI_HEADER, data=json.dumps(data))
                response_json = response.json()
                print(response_json)
                self.middle_summary_state = response_json["choices"][0]["message"]["content"]
                print("Finish Calling OPENAI")
            except Exception as e:
                self.middle_summary_state = e
        else:
            # print(error_list)
            self.middle_summary_state = "Something went wrong"

    def openai_setup_window(self):
        self.openai_key_show = not (self.openai_key_show)

    @pc.var
    def check_openai_setup(self):
        return self.OPENAI_API_KEY != ""
    
    @pc.var
    def get_summary(self):
        return self.middle_summary_state

article_box_style = {
    "bg": "rgba(255,255,255, 0.5)",
    "box_shadow": "3px -3px 7px #cccecf, -3px 3px 7px #ffffff",
    "border_radius": "10px",
    "height": "80px",
    "width": "100%",
    "margin_top": "0.75em",
    "align_items": "left"
}

title_style = {
    "padding": "1em",
    "font_weight": "bold",
    "font_size": "0.9em",
}

def article_card(data):
    return \
        pc.container(
            pc.box(
                pc.text(
                    data,
                    style=title_style
                ),
                on_click=[State.summarize(data), State.redirect],
                style=article_box_style,
                _hover={"cursor": "pointer"}
            ),
        )

def home():
    """The home page."""
    # return  pc.center(
    return \
        pc.vstack(
            pc.box(
                pc.flex(
                    pc.link(
                        pc.text(
                            "NewsGPT",
                            font_size="1.5em",
                            font_weight=600,
                            background_image="linear-gradient(271.68deg, #EE756A 0.75%, #756AEE 88.52%)",
                            background_clip="text",
                            margin_left="20px",
                        ),
                        on_click=State.reset_state_and_go_home
                    ),
                    pc.spacer(),
                    pc.hstack(
                        pc.input(
                            placeholder="New Topic?",
                            on_blur=State.set_text,
                            border_radius="10px",
                            width="450px"
                        ),
                        pc.button(
                            "Search",
                            bg="lightgreen",
                            color="black",
                            is_active=True,
                            on_click=State.search,
                            size="sm",
                            border_radius="1em",
                            variant="outline",
                        ),
                    ),
                    pc.spacer(),
                    pc.button(
                        "OpenAI-KEY",
                        bg="lightgreen",
                        color="black",
                        is_active=True,
                        on_click=State.openai_setup_window,
                        size="sm",
                        border_radius="1em",
                        variant="outline",
                        margin_right="20px"
                    ),
                    pc.alert_dialog(
                        pc.alert_dialog_overlay(
                            pc.alert_dialog_content(
                                pc.alert_dialog_header(
                                    "OpenAI API-Key Setup"),
                                pc.alert_dialog_body(
                                    pc.container(
                                        pc.input(
                                            placeholder="OpenAI Key",
                                            on_blur=State.set_openai_key_text,
                                            border_radius="10px",
                                            width="100%",
                                            type_="password",
                                        ),
                                    ),
                                ),
                                pc.alert_dialog_footer(
                                    pc.vstack(
                                        pc.alert(
                                            pc.alert_icon(),
                                            pc.alert_title(
                                                "set api-key   [" +
                                                State.is_valid_code + "]"
                                            ),
                                            status=State.is_valid_code
                                        ),
                                        pc.hstack(
                                            pc.button(
                                                "Submit",
                                                on_click=[State.submit_openai_key, State.reset_state_and_go_home],
                                            ),
                                            pc.button(
                                                "Close",
                                                on_click=State.openai_setup_window,
                                            ),
                                        ),
                                    ),
                                ),
                                align_items="center"
                            ),
                        ),
                        is_open=State.openai_key_show,
                    ),
                    align_items="center"
                ),
                bg="rgba(255,255,255, 0.7)",
                backdrop_filter="blur(10px)",
                padding_y=["0.8em", "0.8em", "0.5em"],
                border_bottom="0.08em solid rgba(32, 32, 32, .3)",
                position="sticky",
                width="80%",
                top="20px",
                z_index="99",
                justify="center",
                border_radius="20px",
            ),
            pc.grid(
                pc.grid_item(pc.spacer(), row_span=5, col_span=1),
                pc.grid_item(
                    pc.vstack(
                        pc.foreach(
                            State.titles,
                            article_card
                        ),
                        overflow="auto",
                        height="875px"
                    ),
                    row_span=5,
                    col_span=3,
                    # bg="rgba(255,255,255, 0.9)",
                    margin_top="3em",
                    border_radius="20px",
                    box_shadow="7px -7px 14px #cccecf, -7px 7px 14px #ffffff"
                ),
                # pc.grid_item(pc.spacer(), row_span=5, col_span=1),
                pc.grid_item(
                    pc.box(
                        pc.html(State.get_summary, padding="10px"),
                        height="875px",
                        width="100%",
                        overflow="auto",
                    ),
                    row_span=5,
                    col_span=3,
                    margin_top="3em",
                    border_radius="20px",
                    margin_left="50px",
                    box_shadow="7px -7px 14px #cccecf, -7px 7px 14px #ffffff"
                ),
                template_rows="repeat(5, 1fr)",
                template_columns="repeat(8, 1fr)",
                width="100%",
            ),
            pc.spacer(),
            background="radial-gradient(circle at 22% 11%,rgba(62, 180, 137,.20),hsla(0,0%,100%,0) 19%),radial-gradient(circle at 82% 25%,rgba(33,150,243,.18),hsla(0,0%,100%,0) 35%),radial-gradient(circle at 25% 61%,rgba(250, 128, 114, .28),hsla(0,0%,100%,0) 55%)",
        )
