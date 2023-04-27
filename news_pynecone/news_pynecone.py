from pcconfig import config
import pynecone as pc

from .home import home, State

# class State(pc.State):
#     """The app state."""
#     pass


# def index() -> pc.Component:
#     return pc.center(
#         pc.vstack(
#             pc.heading("Welcome to Pynecone!", font_size="2em"),
#             pc.box("Get started by editing ", pc.code(filename, font_size="1em")),
#             pc.link(
#                 "Check out our docs!",
#                 href=docs_url,
#                 border="0.1em solid",
#                 padding="0.5em",
#                 border_radius="0.5em",
#                 _hover={
#                     "color": "rgb(107,99,246)",
#                 },
#             ),
#             spacing="1.5em",
#             font_size="2em",
#         ),
#         padding_top="10%",
#     )


# Add state and page to the app.
app = pc.App(state=State, stylesheets=[
        "https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css",
    ],)
app.add_page(home, route="/")
app.compile()
