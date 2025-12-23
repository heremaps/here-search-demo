import sys

if sys.platform == "emscripten":

    async def install():
        import piplite

        packages = [
            "ipywidgets==8.1.8",
            "ipyleaflet==0.20.0",
            "orjson",
            "xyzservices==2025.11.0",
            "emfs:here_search_demo-0.17.6-py3-none-any.whl",
        ]
        await piplite.install(packages, keep_going=True)

else:

    async def install():
        return
