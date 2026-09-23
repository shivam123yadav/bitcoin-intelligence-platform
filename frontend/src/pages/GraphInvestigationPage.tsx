import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Expand,
  RotateCcw,
  Search,
  Share2,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import { graphService } from '@/services';
import { PriorityBadge, StatusBadge } from '@/components/shared';
import type { GraphEdge, GraphNode } from '@/types';

const colors: Record<GraphNode['type'], string> = {
  wallet: '#3b82f6',
  transaction: '#06b6d4',
  ip: '#f5a623',
  cluster: '#8b5cf6',
};

const CANVAS_W = 800;
const CANVAS_H = 520;

/** Deterministic golden-angle spiral layout filling the SVG canvas. */
function layoutGraph(input: GraphNode[]): GraphNode[] {
  const needsLayout = input.some(
    (n) =>
      !Number.isFinite(n.x) ||
      !Number.isFinite(n.y) ||
      (n.x === 0 && n.y === 0)
  );

  if (!needsLayout) return input;

  const cx = CANVAS_W / 2;
  const cy = CANVAS_H / 2;
  const maxR = Math.min(CANVAS_W, CANVAS_H) / 2 - 40;
  const golden = Math.PI * (3 - Math.sqrt(5));

  return input.map((node, i) => {
    if (
      Number.isFinite(node.x) &&
      Number.isFinite(node.y) &&
      !(node.x === 0 && node.y === 0)
    ) {
      return node;
    }

    const t = input.length <= 1 ? 0 : (i + 1) / input.length;
    const r = maxR * Math.sqrt(t);
    const a = i * golden;

    const x = Math.min(
      CANVAS_W - 24,
      Math.max(24, cx + r * Math.cos(a))
    );

    const y = Math.min(
      CANVAS_H - 24,
      Math.max(24, cy + r * Math.sin(a))
    );

    return {
      ...node,
      x,
      y,
    };
  });
}

type Viewport = {
  x: number;
  y: number;
  scale: number;
};

export function GraphInvestigationPage() {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [selected, setSelected] = useState<GraphNode>();
  const [query, setQuery] = useState('');

  const [types, setTypes] = useState<
    Record<GraphNode['type'], boolean>
  >({
    wallet: true,
    transaction: true,
    ip: true,
    cluster: true,
  });

  const [expanded, setExpanded] = useState(false);

  const [view, setView] = useState<Viewport>({
    x: 0,
    y: 0,
    scale: 1,
  });

  const dragStart = useRef<
    { x: number; y: number; view: Viewport } | undefined
  >();

  const svgRef = useRef<SVGSVGElement>(null);

  const hasDragged = useRef(false);

  // ---------------------------------------------------------
  // LOAD GRAPH
  // ---------------------------------------------------------

  useEffect(() => {
    graphService
      .getGraph()
      .then((graph) => {
        const spread = layoutGraph(graph.nodes);

        setNodes(spread);
        setEdges(graph.edges);
      })
      .catch(() => {
        setNodes([]);
        setEdges([]);
      });
  }, []);

  // ---------------------------------------------------------
  // FILTERING
  // ---------------------------------------------------------

  const visibleNodes = useMemo(
    () =>
      nodes.filter(
        (node) =>
          types[node.type] &&
          (!query ||
            `${node.id} ${node.label}`
              .toLowerCase()
              .includes(query.toLowerCase()))
      ),
    [nodes, types, query]
  );

  const ids = useMemo(
    () => new Set(visibleNodes.map((node) => node.id)),
    [visibleNodes]
  );

  const visibleEdges = useMemo(
    () =>
      edges.filter(
        (edge) =>
          ids.has(edge.source) &&
          ids.has(edge.target)
      ),
    [edges, ids]
  );

  const nodeById = useMemo(
    () => new Map(nodes.map((node) => [node.id, node])),
    [nodes]
  );

  // ---------------------------------------------------------
  // SELECTED NODE RELATIONSHIPS
  // ---------------------------------------------------------

  const selectedEdges = selected
    ? edges.filter(
        (edge) =>
          edge.source === selected.id ||
          edge.target === selected.id
      )
    : [];

  /*
   * IDs belonging to the selected node's direct neighborhood.
   *
   * Example:
   *
   *             transaction
   *                  |
   * transaction -- SELECTED -- wallet
   *                  |
   *                  IP
   *
   * All four surrounding entities are considered
   * neighborhood nodes.
   */
  const neighborhoodIds = useMemo(() => {
    if (!selected) {
      return new Set<string>();
    }

    const ids = new Set<string>();

    ids.add(selected.id);

    selectedEdges.forEach((edge) => {
      ids.add(edge.source);
      ids.add(edge.target);
    });

    return ids;
  }, [selected, selectedEdges]);

  /*
   * Labels are hidden while zoomed out because this graph
   * can contain thousands of entities.
   */
  const showLabels = view.scale >= 1.45;

  // ---------------------------------------------------------
  // ZOOM
  // ---------------------------------------------------------

  const zoom = (delta: number) => {
    setView((current) => ({
      ...current,
      scale: Math.min(
        2,
        Math.max(
          0.5,
          current.scale + delta
        )
      ),
    }));
  };

  const zoomRef = useRef(zoom);
  zoomRef.current = zoom;

  useEffect(() => {
    const el = svgRef.current;

    if (!el) return;

    const onWheel = (event: WheelEvent) => {
      event.preventDefault();

      zoomRef.current(
        event.deltaY > 0
          ? -0.1
          : 0.1
      );
    };

    el.addEventListener(
      'wheel',
      onWheel,
      {
        passive: false,
      }
    );

    return () => {
      el.removeEventListener(
        'wheel',
        onWheel
      );
    };
  }, []);

  // ---------------------------------------------------------
  // CANVAS POINTER HANDLERS
  // ---------------------------------------------------------

  const handlePointerDown = (
    event: React.PointerEvent<SVGSVGElement>
  ) => {
    /*
     * Only start dragging when the actual target is
     * the SVG background.
     *
     * This keeps node selection working.
     */
    if (
      event.target !==
      event.currentTarget
    ) {
      return;
    }

    hasDragged.current = false;

    dragStart.current = {
      x: event.clientX,
      y: event.clientY,
      view,
    };

    event.currentTarget.setPointerCapture(
      event.pointerId
    );
  };

  const handlePointerMove = (
    event: React.PointerEvent<SVGSVGElement>
  ) => {
    if (!dragStart.current) return;

    const dx =
      event.clientX -
      dragStart.current.x;

    const dy =
      event.clientY -
      dragStart.current.y;

    if (
      Math.abs(dx) > 3 ||
      Math.abs(dy) > 3
    ) {
      hasDragged.current = true;
    }

    setView({
      ...dragStart.current.view,
      x:
        dragStart.current.view.x +
        dx,
      y:
        dragStart.current.view.y +
        dy,
    });
  };

  const handlePointerUp = (
    event: React.PointerEvent<SVGSVGElement>
  ) => {
    if (
      event.currentTarget.hasPointerCapture(
        event.pointerId
      )
    ) {
      event.currentTarget.releasePointerCapture(
        event.pointerId
      );
    }

    dragStart.current = undefined;

    setTimeout(() => {
      hasDragged.current = false;
    }, 0);
  };

  const handlePointerCancel = (
    event: React.PointerEvent<SVGSVGElement>
  ) => {
    if (
      event.currentTarget.hasPointerCapture(
        event.pointerId
      )
    ) {
      event.currentTarget.releasePointerCapture(
        event.pointerId
      );
    }

    dragStart.current = undefined;
    hasDragged.current = false;
  };

  // ---------------------------------------------------------
  // NODE SELECTION
  // ---------------------------------------------------------

  const handleNodeClick = (
    event: React.MouseEvent<SVGGElement>,
    node: GraphNode
  ) => {
    event.stopPropagation();

    if (hasDragged.current) {
      return;
    }

    setSelected(node);
  };

  // ---------------------------------------------------------
  // RESET
  // ---------------------------------------------------------

  const reset = () => {
    setQuery('');
    setSelected(undefined);
    setExpanded(false);

    setView({
      x: 0,
      y: 0,
      scale: 1,
    });

    setTypes({
      wallet: true,
      transaction: true,
      ip: true,
      cluster: true,
    });
  };

  return (
    <div className="space-y-4 animate-fade-in">

      {/* =====================================================
          PAGE HEADER
      ====================================================== */}

      <div>
        <h1 className="text-xl font-semibold text-ink-100">
          Graph Investigation
        </h1>

        <p className="text-sm text-ink-300 mt-0.5">
          Network-layer observations and blockchain-layer
          entities in one local investigation graph.
        </p>
      </div>

      {/* =====================================================
          FILTER TOOLBAR
      ====================================================== */}

      <div className="panel p-3 flex flex-wrap items-center gap-3">

        <Search
          size={15}
          className="text-ink-400"
        />

        <input
          className="input flex-1 min-w-52"
          value={query}
          onChange={(event) =>
            setQuery(event.target.value)
          }
          placeholder="Find wallet, transaction, IP, or cluster…"
        />

        {(Object.keys(types) as GraphNode['type'][]).map(
          (type) => (
            <label
              key={type}
              className="flex items-center gap-1.5 text-xs text-ink-300 capitalize"
            >
              <input
                type="checkbox"
                checked={types[type]}
                onChange={() =>
                  setTypes({
                    ...types,
                    [type]:
                      !types[type],
                  })
                }
              />

              {type}
            </label>
          )
        )}

        <button
          className="btn-secondary"
          onClick={() =>
            setExpanded(!expanded)
          }
        >
          <Expand size={14} />
          Expand neighbors
        </button>

        <button
          className="btn-ghost"
          onClick={reset}
        >
          <RotateCcw size={14} />
          Reset
        </button>

      </div>

      {/* =====================================================
          GRAPH + SELECTED NODE
      ====================================================== */}

      <div className="grid grid-cols-12 gap-4">

        {/* ===================================================
            GRAPH
        ==================================================== */}

        <div className="panel col-span-9 overflow-hidden">

          {/* GRAPH HEADER */}

          <div className="panel-header">

            <div>
              <div className="panel-title">
                Relationship graph
              </div>

              <div className="panel-subtitle">
                Scroll to zoom; drag the canvas to pan;
                select a node to inspect it
              </div>
            </div>

            <div className="flex items-center gap-3">

              {/* GRAPH COUNTS */}

              <div className="hidden lg:flex items-center gap-2 text-2xs text-ink-500">

                <span>
                  {visibleNodes.length.toLocaleString()}
                  {' '}
                  nodes
                </span>

                <span className="text-ink-700">
                  •
                </span>

                <span>
                  {visibleEdges.length.toLocaleString()}
                  {' '}
                  relationships
                </span>

              </div>

              {/* NEIGHBORHOOD STATUS */}

              {selected && (
                <div className="hidden xl:flex items-center gap-2 text-2xs">

                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />

                  <span className="text-ink-400">
                    Focus:
                  </span>

                  <span className="text-ink-200">
                    {neighborhoodIds.size.toLocaleString()}
                    {' '}
                    entities
                  </span>

                </div>
              )}

              {/* ZOOM */}

              <div className="flex gap-1">

                <button
                  className="btn-ghost"
                  onClick={() =>
                    zoom(-0.15)
                  }
                  aria-label="Zoom out"
                >
                  <ZoomOut size={14} />
                </button>

                <button
                  className="btn-ghost"
                  onClick={() =>
                    zoom(0.15)
                  }
                  aria-label="Zoom in"
                >
                  <ZoomIn size={14} />
                </button>

              </div>

            </div>

          </div>

          {/* GRAPH CANVAS */}

          <div className="p-3 bg-[#070b12] grid-canvas rounded-b-lg">

            <svg
              ref={svgRef}
              className="w-full h-[520px] cursor-grab active:cursor-grabbing select-none"
              viewBox="0 0 800 520"
              onPointerDown={
                handlePointerDown
              }
              onPointerMove={
                handlePointerMove
              }
              onPointerUp={
                handlePointerUp
              }
              onPointerCancel={
                handlePointerCancel
              }
            >

              <g
                transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}
              >

                {/* =================================================
                    EDGES
                ================================================== */}

                {visibleEdges.map((edge) => {

                  const source =
                    nodeById.get(
                      edge.source
                    );

                  const target =
                    nodeById.get(
                      edge.target
                    );

                  if (
                    !source ||
                    !target
                  ) {
                    return null;
                  }

                  const isSelectedEdge =
                    selectedEdges.includes(
                      edge
                    );

                  const isNeighborhoodEdge =
                    selected
                      ? isSelectedEdge
                      : false;

                  /*
                   * Three visual states:
                   *
                   * 1. No selection:
                   *    normal graph
                   *
                   * 2. Selected neighborhood:
                   *    connected edges bright
                   *
                   * 3. Unrelated:
                   *    heavily faded
                   */

                  const edgeOpacity =
                    !selected
                      ? 0.22
                      : isNeighborhoodEdge
                        ? 0.95
                        : 0.045;

                  const edgeWidth =
                    isNeighborhoodEdge
                      ? 2
                      : 0.6;

                  const edgeColor =
                    isNeighborhoodEdge
                      ? '#60a5fa'
                      : '#334155';

                  return (
                    <line
                      key={edge.id}
                      x1={source.x}
                      y1={source.y}
                      x2={target.x}
                      y2={target.y}
                      stroke={edgeColor}
                      strokeWidth={edgeWidth}
                      opacity={edgeOpacity}
                    />
                  );
                })}

                {/* =================================================
                    NODES
                ================================================== */}

                {visibleNodes.map((node) => {

                  const isSelected =
                    selected?.id ===
                    node.id;

                  const isNeighbor =
                    selected
                      ? neighborhoodIds.has(
                          node.id
                        )
                      : false;

                  const isFocused =
                    !selected ||
                    isNeighbor;

                  const showNodeLabel =
                    isSelected ||
                    showLabels;

                  /*
                   * When an entity is selected:
                   *
                   * selected / connected = strong
                   * unrelated = faded
                   */

                  const nodeOpacity =
                    !selected
                      ? 0.78
                      : isSelected
                        ? 1
                        : isNeighbor
                          ? 0.9
                          : 0.10;

                  const nodeRadius =
                    isSelected
                      ? 12
                      : isNeighbor
                        ? 7
                        : 5;

                  return (
                    <g
                      key={node.id}
                      transform={`translate(${node.x},${node.y})`}
                      className="cursor-pointer"
                      onClick={(event) =>
                        handleNodeClick(
                          event,
                          node
                        )
                      }
                    >

                      {/* Invisible hit area */}

                      <circle
                        r={
                          isSelected
                            ? 22
                            : 16
                        }
                        fill="transparent"
                        pointerEvents="all"
                      />

                      {/* Selected node halo */}

                      {isSelected && (
                        <>
                          <circle
                            r="22"
                            fill="none"
                            stroke={
                              colors[
                                node.type
                              ]
                            }
                            strokeWidth="2"
                            opacity="0.18"
                          />

                          <circle
                            r="17"
                            fill="none"
                            stroke={
                              colors[
                                node.type
                              ]
                            }
                            strokeWidth="2"
                            opacity="0.4"
                          />
                        </>
                      )}

                      {/* Neighbor ring */}

                      {!isSelected &&
                        selected &&
                        isNeighbor && (
                          <circle
                            r="9"
                            fill="none"
                            stroke={
                              colors[
                                node.type
                              ]
                            }
                            strokeWidth="1"
                            opacity="0.4"
                          />
                        )}

                      {/* Main node */}

                      <circle
                        r={nodeRadius}
                        fill={
                          colors[
                            node.type
                          ]
                        }
                        opacity={nodeOpacity}
                        stroke={
                          isSelected
                            ? '#ffffff'
                            : isNeighbor &&
                              selected
                              ? '#dbeafe'
                              : 'none'
                        }
                        strokeWidth={
                          isSelected
                            ? 2
                            : isNeighbor &&
                              selected
                              ? 1
                              : 0
                        }
                      />

                      {/* =================================================
                          LABEL
                      ================================================== */}

                      {showNodeLabel && (
                        <g pointerEvents="none">

                          {isSelected && (
                            <rect
                              x="-72"
                              y="18"
                              width="144"
                              height="24"
                              rx="5"
                              fill="#0b111c"
                              stroke={
                                colors[
                                  node.type
                                ]
                              }
                              strokeWidth="1"
                              opacity="0.97"
                            />
                          )}

                          <text
                            y={
                              isSelected
                                ? 34
                                : 18
                            }
                            textAnchor="middle"
                            fill={
                              isSelected
                                ? '#e2e8f0'
                                : '#94a3b8'
                            }
                            fontSize={
                              isSelected
                                ? 10
                                : 8
                            }
                            fontWeight={
                              isSelected
                                ? 500
                                : 400
                            }
                            opacity={
                              isFocused
                                ? 1
                                : 0.12
                            }
                          >
                            {node.label}
                          </text>

                        </g>
                      )}

                    </g>
                  );
                })}

              </g>

            </svg>

          </div>

          {/* ===================================================
              LEGEND
          ==================================================== */}

          <div className="px-4 py-2 border-t border-ink-700 flex gap-3 text-2xs text-ink-400">

            {(Object.keys(colors) as GraphNode['type'][]).map(
              (type) => (
                <span
                  key={type}
                  className="flex items-center gap-1 capitalize"
                >

                  <i
                    className="w-2 h-2 rounded-full"
                    style={{
                      background:
                        colors[type],
                    }}
                  />

                  {type}

                </span>
              )
            )}

            {selected && (
              <span className="ml-auto text-ink-500">
                Unrelated entities faded
              </span>
            )}

          </div>

        </div>

        {/* =====================================================
            SELECTED NODE PANEL
        ====================================================== */}

        <aside className="panel col-span-3">

          <div className="panel-header">

            <div className="panel-title">
              Selected node
            </div>

          </div>

          {selected ? (

            <div className="p-4 space-y-4">

              {/* NODE HEADER */}

              <div className="flex items-start gap-3">

                <div
                  className="w-3 h-3 rounded-full mt-1.5 shrink-0"
                  style={{
                    background:
                      colors[
                        selected.type
                      ],
                    boxShadow:
                      `0 0 10px ${colors[selected.type]}66`,
                  }}
                />

                <div className="min-w-0">

                  <div className="font-mono text-sm text-ink-100 break-all">
                    {selected.label}
                  </div>

                  <div className="text-2xs text-ink-400 capitalize mt-1">
                    {selected.type}
                    {' · '}
                    {selected.connections ??
                      selectedEdges.length}
                    {' related entities'}
                  </div>

                </div>

              </div>

              {/* FOCUS STATUS */}

              <div className="rounded-md border border-ink-700 bg-ink-950/60 px-3 py-2">

                <div className="flex items-center justify-between">

                  <span className="text-2xs uppercase tracking-wide text-ink-500">
                    Graph focus
                  </span>

                  <span className="text-xs text-blue-300">
                    {neighborhoodIds.size}
                  </span>

                </div>

                <div className="text-2xs text-ink-500 mt-1">
                  Selected entity + directly connected
                  entities
                </div>

              </div>

              {/* PRIORITY */}

              {selected.priority && (
                <PriorityBadge
                  priority={
                    selected.priority
                  }
                  score={
                    selected.priorityScore
                  }
                />
              )}

              <div className="divider" />

              {/* OBSERVED RELATIONSHIPS */}

              <div>

                <div className="text-2xs text-ink-400 uppercase tracking-wide">
                  Observed relationships
                </div>

                <div className="mt-1">

                  {selectedEdges
                    .slice(0, 6)
                    .map((edge) => (
                      <div
                        key={edge.id}
                        className="text-xs text-ink-300 py-1 font-mono"
                      >

                        <span className="text-blue-400 mr-1">
                          {edge.source ===
                          selected.id
                            ? '→'
                            : '←'}
                        </span>

                        {edge.source ===
                        selected.id
                          ? edge.target
                          : edge.source}

                      </div>
                    ))}

                </div>

                {selectedEdges.length ===
                  0 && (
                  <div className="text-xs text-ink-500 mt-2">
                    No directly connected
                    relationships.
                  </div>
                )}

                {selectedEdges.length >
                  6 && (
                  <div className="text-2xs text-ink-500 mt-2">
                    Showing 6 of{' '}
                    {selectedEdges.length.toLocaleString()}
                    {' '}
                    relationships
                  </div>
                )}

              </div>

              {/* EVIDENCE */}

              <div>

                <div className="text-2xs text-ink-400 uppercase tracking-wide">
                  Relevant evidence
                </div>

                <p className="text-xs text-ink-300 mt-1 leading-relaxed">
                  Graph connectivity is an
                  observed association for
                  review; it does not establish
                  ownership or intent.
                </p>

              </div>

              {/* EXPANSION STATUS */}

              {expanded && (
                <StatusBadge
                  status="Neighbor expansion active"
                  variant="intel"
                />
              )}

            </div>

          ) : (

            <div className="p-6 text-center text-xs text-ink-400">

              <Share2
                size={20}
                className="mx-auto mb-2"
              />

              <div>
                Select a graph node to
                inspect it.
              </div>

              <div className="text-2xs text-ink-600 mt-1">
                Click any node in the graph
              </div>

            </div>

          )}

        </aside>

      </div>

    </div>
  );
}