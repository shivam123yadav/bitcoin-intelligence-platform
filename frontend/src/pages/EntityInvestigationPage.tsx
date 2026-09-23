import { useEffect, useState } from 'react';
import {
  Activity,
  ArrowRight,
  Globe,
  Network,
  ShieldAlert,
  Wallet,
} from 'lucide-react';

import {
  entityService,
  transactionService,
  leadService,
} from '@/services';

import {
  PriorityBadge,
  ScoreBar,
  StatusBadge,
} from '@/components/shared';

import {
  formatBtc,
  formatNumber,
  formatTimestamp,
} from '@/utils';

import type {
  Evidence,
  ModelFinding,
  PageId,
  Phase5CLead,
  TimelineEvent,
  Transaction,
  WalletEntity,
} from '@/types';

interface Props {
  entityId?: string;
  onNavigate: (page: PageId) => void;
}

export function EntityInvestigationPage({
  entityId,
  onNavigate,
}: Props) {
  const [wallet, setWallet] = useState<WalletEntity>();
  const [finalLead, setFinalLead] = useState<Phase5CLead>();
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [findings, setFindings] = useState<ModelFinding[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [notes, setNotes] = useState('');
  const [loadError, setLoadError] = useState<string | null>(null);

  /*
   * entityId must be a real backend entity ID
   * (for example, a lead's entityId).
   *
   * There is no mock fallback here.
   */
  useEffect(() => {
    if (!entityId) return;

    setWallet(undefined);
    setFinalLead(undefined);
    setLoadError(null);

    Promise.all([
      entityService.getWallet(entityId),
      leadService.getFinalLead(entityId),
      entityService.getEvidence(entityId),
      entityService.getModelFindings(entityId),
      entityService.getTimeline(entityId),
      transactionService.getTransactions(),
    ])
      .then(([w, lead, e, f, t, tx]) => {
        setWallet(w);
        setFinalLead(lead);
        setEvidence(e);
        setFindings(f);
        setTimeline(t);
        setTransactions(tx.slice(0, 5));
      })
      .catch(() => {
        setLoadError(
          `Entity ${entityId} was not found in the backend.`,
        );
      });
  }, [entityId]);

  /*
   * Empty state
   */
  if (!entityId) {
    return (
      <div className="panel p-10 text-center space-y-3">
        <div className="text-sm font-medium text-ink-100">
          No entity selected
        </div>

        <p className="text-xs text-ink-400">
          Open Investigative Leads and click Review on a real lead
          to investigate it here.
        </p>

        <button
          className="btn-primary mx-auto"
          onClick={() => onNavigate('leads')}
        >
          Go to Investigative Leads
          <ArrowRight size={14} />
        </button>
      </div>
    );
  }

  /*
   * Backend error state
   */
  if (loadError) {
    return (
      <div className="panel p-10 text-center space-y-3">
        <div className="text-sm font-medium text-ink-100">
          Entity not found
        </div>

        <p className="text-xs text-ink-400">
          {loadError}
        </p>

        <button
          className="btn-primary mx-auto"
          onClick={() => onNavigate('leads')}
        >
          Back to Investigative Leads
          <ArrowRight size={14} />
        </button>
      </div>
    );
  }

  /*
   * Loading state
   */
  if (!wallet) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="w-6 h-6 border-2 border-signal-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  /*
   * Entity statistics
   *
   * Using objects instead of nested arrays makes the list keys
   * explicit and avoids React key warnings.
   */
  const stats = [
    {
      label: 'Transactions',
      value: formatNumber(wallet.transactions),
      icon: <Activity size={15} />,
    },
    {
      label: 'Volume observed',
      value: formatBtc(wallet.totalVolumeBtc),
      icon: <Wallet size={15} />,
    },
    {
      label: 'IP observations',
      value: formatNumber(wallet.observedIps),
      icon: <Globe size={15} />,
    },
    {
      label: 'Connected wallets',
      value: formatNumber(wallet.connectedWallets),
      icon: <Network size={15} />,
    },
  ];

  return (
    <div className="space-y-4 animate-fade-in">

      {/* =========================================================
          ENTITY HEADER
      ========================================================= */}

      <div className="flex justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-ink-100 font-mono">
              {wallet.id}
            </h1>

            <PriorityBadge
              priority={wallet.priority}
              score={wallet.priorityScore}
            />

            <StatusBadge
              status="Flagged for review"
              variant="warn"
            />
          </div>

          <p className="text-sm text-ink-300 mt-1">
            Wallet entity · Phase 5C investigative priority ·
            evidence requires analyst review
          </p>
        </div>

        <button
          className="btn-primary"
          onClick={() => onNavigate('graph')}
        >
          View in Graph
          <ArrowRight size={14} />
        </button>
      </div>

      {/* =========================================================
          ENTITY STATS
      ========================================================= */}

      <div className="grid grid-cols-4 gap-3">
        {stats.map((stat) => (
          <div
            className="panel p-4"
            key={stat.label}
          >
            <div className="text-signal-400 mb-2">
              {stat.icon}
            </div>

            <div className="text-lg font-semibold text-ink-100">
              {stat.value}
            </div>

            <div className="stat-label mt-1">
              {stat.label}
            </div>
          </div>
        ))}
      </div>

      {/* =========================================================
          PHASE 5C LEAD EXPLANATION
      ========================================================= */}

      {finalLead && (
        <div className="grid grid-cols-12 gap-4">

          <section className="panel col-span-8">
            <div className="panel-header">
              <div>
                <div className="panel-title">
                  Phase 5C Lead Explanation
                </div>

                <div className="panel-subtitle">
                  Observed facts, derived features, validated
                  patterns, and investigative priority
                </div>
              </div>

              <div className="text-lg font-semibold text-signal-300">
                {finalLead.finalPriorityScore.toFixed(2)}
              </div>
            </div>

            <div className="p-4 space-y-3">
              <p className="text-sm text-ink-200 leading-relaxed">
                {finalLead.explanation}
              </p>

              <div className="grid grid-cols-4 gap-2">
                {[
                  {
                    label: 'Anomaly',
                    value: finalLead.signalBreakdown.anomalyScore,
                  },
                  {
                    label: 'Graph risk',
                    value: finalLead.signalBreakdown.propagatedRisk,
                  },
                  {
                    label: 'Pattern evidence',
                    value:
                      finalLead.signalBreakdown
                        .patternEvidenceScore,
                  },
                  {
                    label: 'Graph context',
                    value:
                      finalLead.signalBreakdown
                        .graphContextScore,
                  },
                ].map((signal) => (
                  <div
                    key={signal.label}
                    className="bg-ink-800 border border-ink-700 rounded-md p-2"
                  >
                    <div className="text-2xs text-ink-400">
                      {signal.label}
                    </div>

                    <div className="text-sm font-mono text-ink-100 mt-1">
                      {(Number(signal.value) * 100).toFixed(1)}%
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* Evidence quality */}

          <section className="panel col-span-4">
            <div className="panel-header">
              <div className="panel-title">
                Evidence Quality
              </div>
            </div>

            <div className="p-4 space-y-3 text-xs">

              <div className="flex justify-between">
                <span className="text-ink-400">
                  Classification
                </span>

                <span className="text-ink-100 capitalize">
                  {finalLead.reviewClassification.replace(
                    '_',
                    ' ',
                  )}
                </span>
              </div>

              <div className="flex justify-between">
                <span className="text-ink-400">
                  Evidence completeness
                </span>

                <span className="text-ink-100">
                  {(
                    finalLead.signalBreakdown
                      .evidenceCompleteness * 100
                  ).toFixed(0)}
                  %
                </span>
              </div>

              <div className="flex justify-between">
                <span className="text-ink-400">
                  Top-K stability
                </span>

                <span className="text-ink-100">
                  {(
                    finalLead.signalBreakdown.topKStability *
                    100
                  ).toFixed(1)}
                  %
                </span>
              </div>

              <div className="flex justify-between">
                <span className="text-ink-400">
                  Effective signal groups
                </span>

                <span className="text-ink-100">
                  {
                    finalLead.signalBreakdown
                      .independentSignalGroups
                  }
                </span>
              </div>

              <div className="divider" />

              <div className="text-2xs text-ink-400">
                {finalLead.scoreSemantics}
              </div>
            </div>
          </section>
        </div>
      )}

      {/* =========================================================
          VALIDATED PATTERNS + WARNINGS
      ========================================================= */}

      {finalLead && (
        <div className="grid grid-cols-12 gap-4">

          <section className="panel col-span-7">
            <div className="panel-header">
              <div className="panel-title">
                Validated Behavioral Patterns
              </div>
            </div>

            <div className="p-4 space-y-2">

              {finalLead.validatedPatterns.length ? (
                finalLead.validatedPatterns.map(
                  (pattern, index) => (
                    <div
                      key={`${pattern.patternType}-${pattern.instanceCount}-${index}`}
                      className="p-3 bg-ink-800 border border-ink-700 rounded-md"
                    >
                      <div className="flex justify-between">
                        <span className="text-xs font-medium text-ink-100">
                          {pattern.patternType
                            .split('_')
                            .join(' ')}
                        </span>

                        <span className="text-2xs text-signal-300">
                          {pattern.instanceCount} instances
                        </span>
                      </div>

                      <div className="text-2xs text-ink-400 mt-1">
                        {(
                          pattern.meanConfidenceScore *
                          100
                        ).toFixed(0)}
                        % confidence ·{' '}

                        {(
                          pattern.meanEvidenceSupportScore *
                          100
                        ).toFixed(0)}
                        % evidence support ·{' '}

                        {pattern.supportingTransactionCount}{' '}
                        transactions
                      </div>
                    </div>
                  ),
                )
              ) : (
                <div className="text-xs text-ink-400">
                  No promoted behavioral patterns attached.
                </div>
              )}

            </div>
          </section>

          {/* Review warnings */}

          <section className="panel col-span-5">
            <div className="panel-header">
              <div className="panel-title">
                Review Warnings
              </div>
            </div>

            <div className="p-4 space-y-2">

              {finalLead.warnings.length ? (
                finalLead.warnings.map((warning) => (
                  <div
                    key={warning}
                    className="text-xs text-warn-300 bg-warn-500/5 border border-warn-500/20 rounded-md p-2"
                  >
                    {warning}
                  </div>
                ))
              ) : (
                <div className="text-xs text-ink-400">
                  No additional review warnings.
                </div>
              )}

            </div>
          </section>
        </div>
      )}

      {/* =========================================================
          EVIDENCE + ENTITY PROFILE
      ========================================================= */}

      <div className="grid grid-cols-12 gap-4">

        <div className="panel col-span-8">
          <div className="panel-header">
            <div>
              <div className="panel-title">
                Why this entity was flagged
              </div>

              <div className="panel-subtitle">
                Model findings, behavioral signals, and observed
                associations
              </div>
            </div>
          </div>

          <div className="p-4 space-y-3">
            {evidence.map((item) => (
              <div
                key={item.id}
                className="p-3 bg-ink-800 border border-ink-700 rounded-md"
              >
                <div className="flex justify-between">
                  <span className="text-xs font-medium text-ink-100">
                    {item.title}
                  </span>

                  <StatusBadge
                    status={item.kind.replace('_', ' ')}
                    variant={
                      item.kind === 'anomalous_behavior'
                        ? 'warn'
                        : item.kind ===
                            'observed_association'
                          ? 'intel'
                          : 'ml'
                    }
                  />
                </div>

                <p className="text-xs text-ink-300 mt-1">
                  {item.description}
                </p>

                <span className="text-2xs text-ink-400">
                  {item.metric}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Entity profile */}

        <div className="panel col-span-4">
          <div className="panel-header">
            <div className="panel-title">
              Entity profile
            </div>
          </div>

          <div className="p-4 space-y-3">

            <div>
              <div className="text-2xs text-ink-400">
                Anomaly score
              </div>

              <ScoreBar
                value={wallet.anomalyScore}
                color="critical"
                label={wallet.mlAnomalyLabel}
              />
            </div>

            <div className="divider" />

            <div className="text-xs text-ink-300">
              Countries observed:{' '}
              <span className="text-ink-100">
                {wallet.countriesList.join(', ')}
              </span>
            </div>

            <div className="text-xs text-ink-300">
              First seen:{' '}
              <span className="text-ink-100">
                {formatTimestamp(wallet.firstSeen)}
              </span>
            </div>

          </div>
        </div>
      </div>

      {/* =========================================================
          TIMELINE + MODEL FINDINGS
      ========================================================= */}

      <div className="grid grid-cols-12 gap-4">

        <section className="panel col-span-7">
          <div className="panel-header">
            <div className="panel-title">
              Transaction timeline
            </div>
          </div>

          <div className="p-4 space-y-3">

            {timeline.map((event) => (
              <div
                className="flex gap-3"
                key={event.id}
              >
                <div className="w-2 h-2 bg-signal-500 rounded-full mt-1.5" />

                <div>
                  <div className="text-xs text-ink-100 font-mono">
                    {event.txId} · {formatBtc(event.amount)}
                  </div>

                  <div className="text-2xs text-ink-400">
                    {formatTimestamp(event.timestamp)} ·{' '}
                    {event.direction} ·{' '}
                    {event.relatedEntity}
                  </div>
                </div>
              </div>
            ))}

          </div>
        </section>

        {/* Model findings */}

        <section className="panel col-span-5">
          <div className="panel-header">
            <div className="panel-title">
              Model findings
            </div>
          </div>

          <div className="p-4 space-y-3">

            {findings.map((finding) => (
              <div
                key={finding.model}
              >
                <div className="flex justify-between text-xs">
                  <span className="text-ink-100">
                    {finding.model}
                  </span>

                  <span className="text-ml-400 font-mono">
                    {finding.value}
                  </span>
                </div>

                <div className="text-2xs text-ink-300 mt-1">
                  {finding.description}
                </div>
              </div>
            ))}

          </div>
        </section>
      </div>

      {/* =========================================================
          RECENT TRANSACTIONS + NOTES
      ========================================================= */}

      <div className="grid grid-cols-12 gap-4">

        <section className="panel col-span-7">
          <div className="panel-header">
            <div className="panel-title">
              Recent transactions
            </div>
          </div>

          <div className="p-4 space-y-2">

            {transactions.map((transaction) => (
              <div
                key={transaction.id}
                className="flex justify-between text-xs"
              >
                <span className="font-mono text-signal-400">
                  {transaction.id}
                </span>

                <span className="text-ink-300">
                  {formatBtc(transaction.amount)} ·{' '}
                  {transaction.srcIp}
                </span>
              </div>
            ))}

          </div>
        </section>

        {/* Investigation notes */}

        <section className="panel col-span-5">
          <div className="panel-header">
            <div className="panel-title">
              Investigation notes
            </div>
          </div>

          <div className="p-4">

            <textarea
              className="input w-full h-24"
              value={notes}
              onChange={(event) =>
                setNotes(event.target.value)
              }
              placeholder="Local analyst notes (not persisted)…"
            />

            <div className="text-2xs text-ink-400 mt-2">
              Notes remain in local frontend state for this
              session.
            </div>

          </div>
        </section>
      </div>

    </div>
  );
}