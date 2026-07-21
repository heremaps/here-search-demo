---
hide-toc: true
---

# Appendix

Miscellaneous developer utilities that are not part of the demo widgets.

## Inject a lat/lon using geojs.io

`here-search-demo` facilitates the use of the services from [geojs.io][2] to discover the location behind an IP address.
The `get_lat_lon` helper is not used in the demo widgets. If you need to inject the geolocation associated with 
your IP, please check the [GeoJS Terms Of Service][3].

   ```
   from here_search_demo.util import get_lat_lon
   latitude, longitude = await get_lat_lon()
   ```

[2]: https://www.geojs.io/
[3]: https://www.geojs.io/tos/
