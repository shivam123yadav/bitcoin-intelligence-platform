from fastapi import APIRouter, HTTPException, Query
import logging

from app.models.schemas import GraphNeighborhoodResponse, GraphStatisticsResponse
from app.services.graph import EntityNotFoundError, GraphDataError, GraphService


logger = logging.getLogger("bitcoin-intelligence-backend")

router = APIRouter(prefix="/api/v1/graph")
graph_service = GraphService()


def _parse_filters(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {item.strip() for item in value.split(",") if item.strip()}


@router.get("/statistics", response_model=GraphStatisticsResponse)
def get_graph_statistics() -> GraphStatisticsResponse:
    try:
        return GraphStatisticsResponse(**graph_service.statistics())
    except GraphDataError as exc:
        logger.error("Graph statistics failed: %s", exc)
        raise HTTPException(
            status_code=500, detail="Graph statistics are unavailable"
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected graph statistics error")
        raise HTTPException(
            status_code=500, detail="Graph statistics are unavailable"
        ) from exc


@router.get(
    "/neighborhood/{entity_type}/{entity_id}",
    response_model=GraphNeighborhoodResponse,
)
def get_graph_neighborhood(
    entity_type: str,
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
