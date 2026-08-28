import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import View, ViewItem
from app.services.errors import NotFoundError, ValidationError


class ViewService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_view(
        self,
        name: str,
        view_type: str,
        root_object_id: uuid.UUID | None = None,
        settings: dict[str, Any] | None = None,
    ) -> View:
        view = View(
            name=name,
            view_type=view_type,
            root_object_id=root_object_id,
            settings_=settings or {},
        )
        self._session.add(view)
        self._session.flush()
        return view

    def create_view_item(
        self,
        view_id: uuid.UUID,
        object_id: uuid.UUID | None = None,
        visual_id: uuid.UUID | None = None,
        x: float | None = None,
        y: float | None = None,
        width: float | None = None,
        height: float | None = None,
        collapsed: bool = False,
        settings: dict[str, Any] | None = None,
    ) -> ViewItem:
        if object_id is None and visual_id is None:
            raise ValidationError("view item requires object_id or visual_id")
        if object_id is not None and visual_id is not None:
            raise ValidationError("view item cannot have both object_id and visual_id")

        if self._session.get(View, view_id) is None:
            raise NotFoundError("view", view_id)

        item = ViewItem(
            view_id=view_id,
            object_id=object_id,
            visual_id=visual_id,
            x=x,
            y=y,
            width=width,
            height=height,
            collapsed=collapsed,
            settings_=settings or {},
        )
        self._session.add(item)
        self._session.flush()
        return item

    def update_item_position(self, item_id: uuid.UUID, x: float, y: float) -> ViewItem:
        item = self._session.get(ViewItem, item_id)
        if item is None:
            raise NotFoundError("view_item", item_id)
        item.x = x
        item.y = y
        self._session.flush()
        return item

    def delete_view(self, view_id: uuid.UUID) -> None:
        view = self._session.get(View, view_id)
        if view is None:
            raise NotFoundError("view", view_id)
        self._session.delete(view)
        self._session.flush()
        self._session.expire_all()

    def list_view_items(self, view_id: uuid.UUID) -> list[ViewItem]:
        return list(
            self._session.scalars(select(ViewItem).where(ViewItem.view_id == view_id)).all()
        )
