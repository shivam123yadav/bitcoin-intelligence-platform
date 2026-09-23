import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from 'react';

import {
  Upload,
  FileText,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Database,
  HardDrive,
  Clock,
  Globe,
  Server,
  Copy,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

import { datasetService } from '@/services';
import { StatusBadge } from '@/components/shared';
import {
  formatNumber,
  formatBytes,
  formatTimestamp,
  formatDate,
} from '@/utils';

import type {
  DatasetMeta,
  DatasetStats,
  DatasetFieldQuality,
  DatasetPreviewRow,
  DatasetCatalog,
} from '@/types';

export function DatasetPage() {
  const [meta, setMeta] = useState<DatasetMeta | null>(null);
  const [stats, setStats] = useState<DatasetStats | null>(null);
  const [quality, setQuality] = useState<DatasetFieldQuality[]>([]);
  const [preview, setPreview] = useState<DatasetPreviewRow[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [catalog, setCatalog] = useState<DatasetCatalog | null>(null);

  const [uploadState, setUploadState] = useState<
    'idle' | 'uploading' | 'success' | 'error'
  >('idle');

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const MAX_FILE_SIZE = 500 * 1024 * 1024;

  const ACCEPTED_EXTENSIONS = ['.csv', '.json', '.xml'];

  useEffect(() => {
    (async () => {
      try {
        const [m, s, q, p, c] = await Promise.all([
          datasetService.getMeta(),
          datasetService.getStats(),
          datasetService.getFieldQuality(),
          datasetService.getPreview(1, 8),
          datasetService.getCatalog(),
        ]);

        setMeta(m);
        setStats(s);
        setQuality(q);
        setPreview(p.rows);
        setTotal(p.total);
        setCatalog(c);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!loading) {
      datasetService
        .getPreview(page, 8)
        .then((p) => setPreview(p.rows));
    }
  }, [page, loading]);

  /*
   * Open the native Windows file picker.
   */
  function openFilePicker() {
    if (uploadState === 'uploading') {
      return;
    }

    fileInputRef.current?.click();
  }

  /*
   * Validate the selected file.
   */
  function validateFile(file: File): string | null {
    const filename = file.name.toLowerCase();

    const hasValidExtension = ACCEPTED_EXTENSIONS.some((extension) =>
      filename.endsWith(extension),
    );

    if (!hasValidExtension) {
      return 'Unsupported file format. Please select a CSV, JSON, or XML file.';
    }

    if (file.size > MAX_FILE_SIZE) {
      return 'File is too large. The maximum allowed size is 500 MB.';
    }

    return null;
  }

  /*
   * Start the existing demo upload flow after a real file
   * has actually been selected.
   */
  async function processSelectedFile(file: File) {
    const validationError = validateFile(file);

    if (validationError) {
      setSelectedFile(null);
      setUploadError(validationError);
      setUploadState('error');
      return;
    }

    setSelectedFile(file);
    setUploadError(null);
    setUploadState('uploading');

    try {
      const result = await datasetService.upload(file);
      const nextCatalog = await datasetService.getCatalog();
      setCatalog(nextCatalog);
      setUploadState('success');
      setUploadError(null);
      // A newly uploaded dataset is intentionally stored but not made active.
      // The current investigation remains on the analyzed dataset until a
      // future analysis run makes the uploaded dataset selectable.
      setTimeout(() => setUploadState('idle'), 3000);
      setSelectedFile(file);
      console.info(result.message, result.dataset.id);
    } catch (error) {
      setUploadState('error');
      setUploadError(error instanceof Error ? error.message : 'Dataset upload failed.');
    }
  }

  /*
   * Handle file picker selection.
   */
  function handleFileChange(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    processSelectedFile(file);

    /*
     * Reset the input so selecting the same file again
     * still triggers onChange.
     */
    event.target.value = '';
  }

  /*
   * Handle drag enter.
   */
  function handleDragEnter(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();

    if (uploadState !== 'uploading') {
      setIsDragging(true);
    }
  }

  /*
   * Handle drag over.
   */
  function handleDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();

    if (uploadState !== 'uploading') {
      setIsDragging(true);
    }
  }

  /*
   * Handle drag leave.
   */
  function handleDragLeave(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();

    setIsDragging(false);
  }

  /*
   * Handle dropped file.
   */
  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();

    setIsDragging(false);

    if (uploadState === 'uploading') {
      return;
    }

    const file = event.dataTransfer.files?.[0];

    if (!file) {
      return;
    }

    processSelectedFile(file);
  }

  /*
   * Load sample dataset.
   *
   * This remains separate from Select Dataset.
   */
  async function handleLoadSample() {
    if (uploadState === 'uploading') {
      return;
    }

    setSelectedFile(null);
    setUploadError(null);
    setUploadState('uploading');

    try {
      await datasetService.select('synthetic_traffic_v1.0.0');
      const [m, s, q, p, c] = await Promise.all([
        datasetService.getMeta(),
        datasetService.getStats(),
        datasetService.getFieldQuality(),
        datasetService.getPreview(1, 8),
        datasetService.getCatalog(),
      ]);
      setMeta(m); setStats(s); setQuality(q); setPreview(p.rows); setTotal(p.total); setCatalog(c); setPage(1);
      setUploadState('success');
      setTimeout(() => setUploadState('idle'), 2500);
    } catch (error) {
      setUploadState('error');
      setUploadError(error instanceof Error ? error.message : 'Unable to load the sample dataset.');
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="w-6 h-6 border-2 border-signal-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const statItems = [
    {
      label: 'Transactions',
      value: stats!.transactions,
      icon: <FileText size={14} />,
    },
    {
      label: 'Wallets',
      value: stats!.wallets,
      icon: <Database size={14} />,
    },
    {
      label: 'IPs',
      value: stats!.ips,
      icon: <Globe size={14} />,
    },
    {
      label: 'Countries',
      value: stats!.countries,
      icon: <Globe size={14} />,
    },
    {
      label: 'ASNs',
      value: stats!.asns,
      icon: <Server size={14} />,
    },
    {
      label: 'Valid Records',
      value: stats!.validRecords,
      icon: <CheckCircle2 size={14} />,
    },
    {
      label: 'Invalid Records',
      value: stats!.invalidRecords,
      icon: <XCircle size={14} />,
    },
    {
      label: 'Duplicates',
      value: stats!.duplicates,
      icon: <Copy size={14} />,
    },
  ];

  const pageSize = 8;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-4 animate-fade-in">

      {/* =========================================================
          PAGE HEADER
      ========================================================= */}

      <div>
        <h1 className="text-xl font-semibold text-ink-100 tracking-tight">
          Dataset Management
        </h1>

        <p className="text-sm text-ink-300 mt-0.5">
          Upload, validate, and inspect transaction metadata
        </p>
      </div>

      {/* =========================================================
          UPLOAD AREA
      ========================================================= */}

      <div className="grid grid-cols-12 gap-4">

        <div className="panel col-span-8">

          <div className="panel-header">
            <div>
              <div className="panel-title">
                Upload Dataset
              </div>

              <div className="panel-subtitle">
                Supports CSV, JSON, and XML formats
              </div>
            </div>
          </div>

          <div className="p-6">

            {/* Hidden native file input */}

            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.json,.xml,text/csv,application/json,text/xml,application/xml"
              className="hidden"
              onChange={handleFileChange}
            />

            {/* Drop zone */}

            <div
              role="button"
              tabIndex={uploadState === 'uploading' ? -1 : 0}
              onClick={openFilePicker}
              onKeyDown={(event) => {
                if (
                  event.key === 'Enter' ||
                  event.key === ' '
                ) {
                  event.preventDefault();
                  openFilePicker();
                }
              }}
              onDragEnter={handleDragEnter}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-all cursor-pointer ${
                uploadState === 'uploading'
                  ? 'border-signal-500 bg-signal-500/5 cursor-wait'
                  : uploadState === 'success'
                    ? 'border-ok-500 bg-ok-500/5'
                    : uploadState === 'error'
                      ? 'border-critical-500 bg-critical-500/5'
                      : isDragging
                        ? 'border-signal-400 bg-signal-500/10'
                        : 'border-ink-600 hover:border-signal-500 bg-ink-800/50'
              }`}
            >

              {/* Idle */}

              {uploadState === 'idle' && (
                <>
                  <Upload
                    size={32}
                    className="mx-auto text-ink-400 mb-3"
                  />

                  <p className="text-sm text-ink-200 font-medium">
                    Drop CSV / JSON / XML dataset
                  </p>

                  <p className="text-xs text-ink-400 mt-1">
                    or click here to select a file
                  </p>

                  {selectedFile && (
                    <div className="mt-3 text-xs text-signal-400">
                      Selected: {selectedFile.name}
                    </div>
                  )}
                </>
              )}

              {/* Uploading */}

              {uploadState === 'uploading' && (
                <>
                  <div className="w-8 h-8 border-2 border-signal-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />

                  <p className="text-sm text-signal-400 font-medium">
                    Uploading and validating…
                  </p>

                  {selectedFile && (
                    <p className="text-xs text-ink-400 mt-1">
                      {selectedFile.name}
                    </p>
                  )}
                </>
              )}

              {/* Success */}

              {uploadState === 'success' && (
                <>
                  <CheckCircle2
                    size={32}
                    className="mx-auto text-ok-400 mb-3"
                  />

                  <p className="text-sm text-ok-400 font-medium">
                    Dataset uploaded successfully
                  </p>

                  <p className="text-xs text-ink-400 mt-1">
                    Validation passed — 48,521 records
                  </p>

                  {selectedFile && (
                    <p className="text-xs text-ink-400 mt-1">
                      {selectedFile.name}
                    </p>
                  )}
                </>
              )}

              {/* Error */}

              {uploadState === 'error' && (
                <>
                  <AlertTriangle
                    size={32}
                    className="mx-auto text-critical-400 mb-3"
                  />

                  <p className="text-sm text-critical-400 font-medium">
                    File could not be selected
                  </p>

                  <p className="text-xs text-ink-400 mt-1">
                    {uploadError}
                  </p>

                  <p className="text-xs text-signal-400 mt-3">
                    Click to choose another file
                  </p>
                </>
              )}

            </div>

            {/* Buttons */}

            <div className="flex items-center gap-3 mt-4">

              <button
                type="button"
                onClick={openFilePicker}
                className="btn-primary"
                disabled={uploadState === 'uploading'}
              >
                <Upload size={14} />
                Select Dataset
              </button>

              <button
                type="button"
                onClick={handleLoadSample}
                className="btn-secondary"
                disabled={uploadState === 'uploading'}
              >
                <FileText size={14} />
                Load Sample Dataset
              </button>

              <span className="text-2xs text-ink-400 ml-auto">
                Max file size: 500 MB
              </span>

            </div>

            {/* Selected file information */}

            {selectedFile &&
              uploadState === 'idle' && (
                <div className="mt-3 flex items-center gap-2 text-xs text-ink-400">
                  <FileText size={13} />

                  <span>
                    {selectedFile.name}
                  </span>

                  <span>
                    ·
                  </span>

                  <span>
                    {formatBytes(selectedFile.size)}
                  </span>
                </div>
              )}

          </div>
        </div>

        {/* =======================================================
            CURRENT DATASET
        ======================================================= */}

        <div className="panel col-span-4">

          <div className="panel-header">
            <div>
              <div className="panel-title">
                Current Dataset
              </div>

              <div className="panel-subtitle">
                Active dataset details
              </div>
            </div>
          </div>

          <div className="p-4 space-y-3">

            <div className="flex items-center gap-3 p-3 rounded-md bg-ink-800 border border-ink-700">

              <FileText
                size={20}
                className="text-signal-400"
              />

              <div className="flex-1 min-w-0">

                <div className="text-xs font-mono text-ink-100 truncate">
                  {meta!.filename}
                </div>

                <div className="text-2xs text-ink-400 mt-0.5">
                  {formatBytes(meta!.fileSizeBytes)} ·{' '}
                  {meta!.format.toUpperCase()}
                </div>

              </div>
            </div>

            <div className="space-y-2">

              <DataRow
                icon={<FileText size={12} />}
                label="Records"
                value={formatNumber(meta!.records)}
              />

              <DataRow
                icon={<Clock size={12} />}
                label="Time Range"
                value={`${formatDate(
                  meta!.timeRangeStart,
                )} — ${formatDate(meta!.timeRangeEnd)}`}
              />

              <DataRow
                icon={<HardDrive size={12} />}
                label="File Size"
                value={formatBytes(meta!.fileSizeBytes)}
              />

              <DataRow
                icon={<Clock size={12} />}
                label="Uploaded"
                value={formatTimestamp(meta!.uploadedAt)}
              />

              <div className="flex items-center justify-between py-1.5">

                <span className="text-2xs text-ink-400">
                  Validation
                </span>

                <StatusBadge
                  status="Valid"
                  variant="ok"
                />

              </div>
            </div>
          </div>
        </div>
      </div>

      {/* =========================================================
          DATASET STATISTICS
      ========================================================= */}

      <div className="panel">

        <div className="panel-header">

          <div>
            <div className="panel-title">
              Dataset Statistics
            </div>

            <div className="panel-subtitle">
              Summary of ingested data
            </div>
          </div>

        </div>

        <div className="grid grid-cols-8 gap-px bg-ink-700">

          {statItems.map((item) => (
            <div
              key={item.label}
              className="bg-ink-850 p-4"
            >
              <div className="flex items-center gap-2 text-ink-400 mb-2">
                {item.icon}
              </div>

              <div className="text-lg font-semibold text-ink-100 tabular-nums">
                {formatNumber(item.value)}
              </div>

              <div className="text-2xs text-ink-400 mt-0.5">
                {item.label}
              </div>
            </div>
          ))}

        </div>
      </div>

      {/* =========================================================
          DATA QUALITY
      ========================================================= */}

      <div className="panel">

        <div className="panel-header">

          <div>
            <div className="panel-title">
              Data Quality
            </div>

            <div className="panel-subtitle">
              Field-level coverage and validation
            </div>
          </div>

        </div>

        <div className="overflow-x-auto">

          <table className="w-full text-xs">

            <thead>
              <tr className="border-b border-ink-700 text-ink-400">

                <th className="px-4 py-2.5 text-left font-medium">
                  Field
                </th>

                <th className="px-4 py-2.5 text-left font-medium">
                  Coverage
                </th>

                <th className="px-4 py-2.5 text-left font-medium">
                  Invalid
                </th>

                <th className="px-4 py-2.5 text-left font-medium">
                  Status
                </th>

              </tr>
            </thead>

            <tbody>

              {quality.map((q) => (
                <tr
                  key={q.field}
                  className="border-b border-ink-700/50 table-row-hover"
                >

                  <td className="px-4 py-2.5 font-mono text-ink-100">
                    {q.field}
                  </td>

                  <td className="px-4 py-2.5">

                    <div className="flex items-center gap-2">

                      <div className="w-24 h-1.5 bg-ink-700 rounded-full overflow-hidden">

                        <div
                          className={`h-full rounded-full ${
                            q.status === 'good'
                              ? 'bg-ok-500'
                              : q.status === 'warning'
                                ? 'bg-warn-500'
                                : 'bg-critical-500'
                          }`}
                          style={{
                            width: `${q.coverage}%`,
                          }}
                        />

                      </div>

                      <span className="text-ink-300 tabular-nums">
                        {q.coverage.toFixed(1)}%
                      </span>

                    </div>

                  </td>

                  <td className="px-4 py-2.5 tabular-nums text-ink-300">
                    {q.invalid}
                  </td>

                  <td className="px-4 py-2.5">

                    {q.status === 'good' ? (
                      <StatusBadge
                        status="Good"
                        variant="ok"
                      />
                    ) : q.status === 'warning' ? (
                      <StatusBadge
                        status="Warning"
                        variant="warn"
                      />
                    ) : (
                      <StatusBadge
                        status="Critical"
                        variant="critical"
                      />
                    )}

                  </td>

                </tr>
              ))}

            </tbody>

          </table>

        </div>
      </div>

      {/* =========================================================
          DATASET PREVIEW
      ========================================================= */}

      <div className="panel">

        <div className="panel-header">

          <div>
            <div className="panel-title">
              Dataset Preview
            </div>

            <div className="panel-subtitle">
              Paginated view of raw records
            </div>
          </div>

          <span className="text-2xs text-ink-400">
            {total === 0
              ? '0'
              : (page - 1) * pageSize + 1}
            –
            {Math.min(page * pageSize, total)} of {total}
          </span>

        </div>

        <div className="overflow-x-auto">

          <table className="w-full text-xs">

            <thead>

              <tr className="border-b border-ink-700 text-ink-400">

                <th className="px-3 py-2.5 text-left font-medium">
                  #
                </th>

                <th className="px-3 py-2.5 text-left font-medium">
                  Timestamp
                </th>

                <th className="px-3 py-2.5 text-left font-medium">
                  Src IP
                </th>

                <th className="px-3 py-2.5 text-left font-medium">
                  Dst IP
                </th>

                <th className="px-3 py-2.5 text-left font-medium">
                  Ports
                </th>

                <th className="px-3 py-2.5 text-left font-medium">
                  TXID
                </th>

                <th className="px-3 py-2.5 text-left font-medium">
                  Inputs
                </th>

                <th className="px-3 py-2.5 text-left font-medium">
                  Outputs
                </th>

                <th className="px-3 py-2.5 text-left font-medium">
                  Amount
                </th>

                <th className="px-3 py-2.5 text-left font-medium">
                  Fee
                </th>

                <th className="px-3 py-2.5 text-left font-medium">
                  Script
                </th>

              </tr>

            </thead>

            <tbody>

              {preview.map((row) => (
                <tr
                  key={row.id}
                  className="border-b border-ink-700/50 table-row-hover"
                >

                  <td className="px-3 py-2 font-mono text-ink-400">
                    {row.id}
                  </td>

                  <td className="px-3 py-2 font-mono text-2xs text-ink-300">
                    {formatTimestamp(row.timestamp)}
                  </td>

                  <td className="px-3 py-2 font-mono text-2xs text-ink-200">
                    {row.src_ip}
                  </td>

                  <td className="px-3 py-2 font-mono text-2xs text-ink-200">
                    {row.dst_ip}
                  </td>

                  <td className="px-3 py-2 font-mono text-2xs text-ink-400">
                    {row.src_port}→{row.dst_port}
                  </td>

                  <td className="px-3 py-2 font-mono text-2xs text-signal-400">
                    {row.txid}
                  </td>

                  <td className="px-3 py-2 font-mono text-2xs text-ink-300">
                    {row.input_addresses.length}
                  </td>

                  <td className="px-3 py-2 font-mono text-2xs text-ink-300">
                    {row.output_addresses.length}
                  </td>

                  <td className="px-3 py-2 font-mono text-ink-100 tabular-nums">
                    {row.input_amounts
                      .reduce((a, b) => a + b, 0)
                      .toFixed(2)}
                  </td>

                  <td className="px-3 py-2 font-mono text-2xs text-ink-400 tabular-nums">
                    {row.fee.toFixed(5)}
                  </td>

                  <td className="px-3 py-2">
                    <span className="text-2xs text-ink-300 bg-ink-700/60 px-1.5 py-0.5 rounded">
                      {row.script_type}
                    </span>
                  </td>

                </tr>
              ))}

            </tbody>

          </table>

        </div>

        {/* Pagination */}

        <div className="flex items-center justify-between px-4 py-3 border-t border-ink-700">

          <span className="text-2xs text-ink-400">
            Page {page} of {totalPages}
          </span>

          <div className="flex items-center gap-1">

            <button
              type="button"
              onClick={() =>
                setPage(Math.max(1, page - 1))
              }
              disabled={page === 1}
              className="btn-ghost disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft size={14} />
            </button>

            <button
              type="button"
              onClick={() =>
                setPage(
                  Math.min(totalPages, page + 1),
                )
              }
              disabled={page === totalPages}
              className="btn-ghost disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronRight size={14} />
            </button>

          </div>

        </div>
      </div>


      {/* Stored datasets */}
      <div className="panel mt-4">
        <div className="panel-header">
          <div>
            <div className="panel-title">Stored Datasets</div>
            <div className="panel-subtitle">Persistent dataset catalog on this backend</div>
          </div>
          <span className="text-2xs text-ink-400">{catalog?.datasets.length ?? 0} dataset(s)</span>
        </div>
        <div className="divide-y divide-ink-700">
          {(catalog?.datasets ?? []).map((dataset) => (
            <div key={dataset.id} className="px-4 py-3 flex items-center gap-3">
              <FileText size={16} className="text-signal-400 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-xs font-mono text-ink-100 truncate">{dataset.filename}</div>
                <div className="text-2xs text-ink-400 mt-0.5">
                  {formatNumber(dataset.records)} records · {dataset.format.toUpperCase()} · {dataset.analysisStatus === 'completed' ? 'Analysis complete' : 'Stored — analysis not run'}
                </div>
              </div>
              {catalog?.activeDatasetId === dataset.id ? (
                <StatusBadge status="Active" variant="ok" />
              ) : (
                <StatusBadge
                  status={dataset.analysisStatus === 'completed' ? 'Ready' : 'Stored'}
                  variant={dataset.analysisStatus === 'completed' ? 'intel' : 'warn'}
                />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function DataRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-2xs text-ink-400 flex items-center gap-1.5">
        {icon}
        {label}
      </span>
      <span className="text-xs text-ink-100 font-mono">
        {value}
      </span>
    </div>
  );
}
