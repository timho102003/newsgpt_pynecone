import pynecone as pc

config = pc.Config(
    app_name="news_pynecone",
    db_url="sqlite:///pynecone.db",
    env=pc.Env.DEV,
)
