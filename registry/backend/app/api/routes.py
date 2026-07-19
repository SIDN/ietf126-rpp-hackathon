"""API routes for registry entries."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.models import Entry, EntryCreate, EntryUpdate
from app.store import EntryNotFoundError, store

router = APIRouter(prefix="/entries", tags=["entries"])


@router.get("", response_model=list[Entry])
def list_entries() -> list[Entry]:
    return store.list()


@router.post("", response_model=Entry, status_code=status.HTTP_201_CREATED)
def create_entry(payload: EntryCreate) -> Entry:
    return store.create(payload)


@router.get("/{entry_id}", response_model=Entry)
def get_entry(entry_id: UUID) -> Entry:
    try:
        return store.get(entry_id)
    except EntryNotFoundError:
        raise HTTPException(status_code=404, detail="Entry not found")


@router.patch("/{entry_id}", response_model=Entry)
def update_entry(entry_id: UUID, payload: EntryUpdate) -> Entry:
    try:
        return store.update(entry_id, payload)
    except EntryNotFoundError:
        raise HTTPException(status_code=404, detail="Entry not found")


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: UUID) -> None:
    try:
        store.delete(entry_id)
    except EntryNotFoundError:
        raise HTTPException(status_code=404, detail="Entry not found")
