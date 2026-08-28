# Current task — PHASE 04

## Goal

Allow the same object to appear in several maps.

## Do

1. Table `views`: id, name, view_type, root_object_id NULL, settings JSONB, created_at, updated_at.
2. Table `view_items`: view_id, object_id NULL, visual_id NULL, x, y, width, height, collapsed, settings JSONB.
3. Coordinates belong to the view, not the object.

## Accept

One task can appear with different coordinates in two views.
