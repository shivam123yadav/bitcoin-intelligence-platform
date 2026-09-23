from fastapi import APIRouter, HTTPException, Query
import logging

from app.api.graph import graph_service
from app.models.schemas import (
    EntityLookupResponse,
    EntityType,
    GraphNeighborhoodResponse,
)
from app.services.graph import EntityNotFoundError, GraphDataError


logger = logging.getLogger("bitcoin-intelligence-backend")

router = APIRouter(prefix="/api/v1/entities")


def _parse_filters(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {item.strip() for item in value.split(",") if item.strip()}


@router.get(
    "/{entity_type}/{entity_id}/neighbors",
    response_model=GraphNeighborhoodResponse,
)
def get_entity_neighbors(
    entity_type: EntityType,
    entity_id: str,
    depth: int = Query(default=1, ge=1, le=2),
    node_types: str | None = Query(default=None),
    edge_types: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> GraphNeighborhoodResponse:
    try:
        return GraphNeighborhoodResponse(
            **graph_service.neighborhood(
                entity_type,
                entity_id,
                depth=depth,
                node_types=_parse_filters(node_types),
                edge_types=_parse_filters(edge_types),
                limit=limit,
            )
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GraphDataError as exc:
        logger.error("Graph neighborhood failed: %s", exc)
        raise HTTPException(
            status_code=500, detail="Graph neighborhood is unavailable"
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected graph neighborhood error")
        raise HTTPException(
            status_code=500, detail="Graph neighborhood is unavailable"
        ) from exc


@router.get("/{entity_type}/{entity_id}", response_model=EntityLookupResponse)
def get_entity(
    entity_type: EntityType,
    entity_id: str,
    limit: int = Query(default=100, ge=1, le=500),
) -> EntityLookupResponse:
    try:
        return EntityLookupResponse(
            **graph_service.entity_summary(entity_type, entity_id, limit=limit)
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GraphDataError as exc:
        logger.error("Entity lookup failed: %s", exc)
        raise HTTPException(
            status_code=500, detail="Entity lookup is unavailable"
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected entity lookup error")
        raise HTTPException(
            status_code=500, detail="Entity lookup is unavailable"
        ) from exc
