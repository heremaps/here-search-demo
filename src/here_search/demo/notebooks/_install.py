import sys

if sys.platform == "emscripten":

    async def install():
        import piplite

        packages = [
            "ipywidgets==8.1.7",
            "ipyleaflet==0.20.0",
            "orjson",
            "emfs:here_search_demo-0.12.0-py3-none-any.whl",
        ]
        await piplite.install(packages, keep_going=True)

else:

    async def install():
        return
