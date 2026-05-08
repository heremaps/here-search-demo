###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################


import asyncio
from here_search_demo.util import AsyncCPUProfiler
from here_search_demo.widgets.app import OneBoxMap


async def main():

    app = OneBoxMap(route_post=True, fuel=True)
    app._running = True
    box = app.query_box_w  # The box inside the app widget
    categories_buttons = app.buttons_box_w.buttons  # The category buttons
    response_items = app.map_w.state.items_data_by_rank # The search response items
    route_ctl = app.map_w.route  # The route controller

    asyncio.create_task(app.handle_search_events())

    print("Set a route start to W Rabdolph 100 in Chicago. Simulate some typo corrections")
    text = "chcago\b\b\b\bicago"
    print(f"q={text.replace('\b', '\\b')}")
    await box.feed(text=text, delay=0.7)
    box.submit()

    await asyncio.sleep(2)
    print(f"{str(response_items)[:100]}")

    text = "w randolph 100"
    print(f"q={text}")
    await box.feed(text=text, delay=0.08)
    box.submit()

    await asyncio.sleep(3)

    route_ctl.set_route_start(tuple(response_items[0]["access"][0].values()))
    route_ctl.set_route_at(tuple(response_items[0]["access"][0].values()))
    route_ctl.set_route_width(400)

    print(f"{str(response_items)[:100]}")

    print("Set a route end to W Roosevelt 3321.")
    text = "w roosevelt 3321"
    print(f"q={text}")
    await box.feed(text=text, delay=0.08)
    box.submit()

    await asyncio.sleep(3)
    print(f"{str(response_items)[:100]}")

    print("Search for gas stations along the route")
    categories_buttons[0].click()

    await asyncio.sleep(2)
    print(f"{str(response_items)[:100]}")

    await app.stop()


if __name__ == "__main__":
    profiler = AsyncCPUProfiler()
    profiler.start()

    asyncio.run(main())

    profiler.stop()
    profiler.report()