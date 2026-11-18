"""Base tile layer selection and replacement for the position map."""

from ipyleaflet import (
    TileLayer,
    basemaps,
)


class BaseLayerMixin:
    """Base tile layer selection and replacement for the position map."""

    def _here_url(self, style: str) -> str:
        return (
            f"https://maps.hereapi.com/v3/base/mc/{{z}}/{{x}}/{{y}}/png"
            f"?style={style}&ppi=400&size=512&apiKey={self._credentials.api_key}&lang={self._preferred_language}"
        )

    def _here_attribution(self) -> str:
        return "© HERE 2026"

    def _mapnik_url(self) -> str:
        return basemaps.OpenStreetMap.Mapnik.build_url()

    def _mapnik_attribution(self) -> str:
        return basemaps.OpenStreetMap.Mapnik.html_attribution

    def _base_layer_url(self, style: str) -> str:
        """Return the HERE tile URL when an API key is available, else Mapnik."""
        if self._credentials.api_key:
            return self._here_url(style)
        return self._mapnik_url()

    def _base_layer_attribution(self) -> str:
        """Return the HERE attribution when an API key is available, else Mapnik."""
        if self._credentials.api_key:
            return self._here_attribution()
        return self._mapnik_attribution()

    def set_base_layer_style(self, style: str) -> None:
        self._base_layer_style = style
        self._replace_base_layer()

    def refresh_base_layer(self) -> None:
        self._replace_base_layer()

    def _replace_base_layer(self) -> None:
        """Rebuild the base tile layer so the attribution control is refreshed.

        Mutating the ``url`` / ``attribution`` traits of an existing
        :class:`~ipyleaflet.TileLayer` reloads the tiles but does not refresh
        Leaflet's attribution control, which only reacts to layer add/remove.
        Moreover the attribution control accumulates strings by reference count
        and does not reliably drop a removed layer's attribution, so we also
        recreate the control to rebuild the attribution from the current layers.
        """
        old_layer = self.base_layer
        opacity = old_layer.opacity
        self.base_layer = TileLayer(
            url=self._base_layer_url(self._base_layer_style),
            attribution=self._base_layer_attribution(),
            opacity=opacity,
        )
        self.add(self.base_layer)
        self.remove(old_layer)
        if self.attribution_control:
            self.attribution_control = False
            self.attribution_control = True
            self._restore_bottom_right_order()

    def _restore_bottom_right_order(self) -> None:
        """Re-stack the bottom-right controls above the attribution control.

        Leaflet inserts each newly added control at the *top* of a bottom
        corner, so recreating the attribution control leaves it above the
        other bottom-right controls. Removing and re-adding those controls in
        their original order pushes them back above the attribution control.
        """
        for control in self._bottom_right_controls:
            if control in self.controls:
                self.remove(control)
            self.add(control)
