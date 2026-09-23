# 08 --- Pattern Detection

## Purpose

Detect transaction-flow structures that may merit analyst review.

This component is separate from the primary anomaly ML model.

## Peeling-chain candidate

Look for sequences characterized by repeated movement through
transactions where: - one output continues forward - amounts change in a
structured way - timing between hops is relevant - the sequence length
exceeds a configurable threshold

Output: - candidate chain - hop count - transaction IDs - wallets -
timestamps - amounts - supporting evidence

## Mixing-like structures

Look for structural characteristics such as: - multiple inputs/outputs -
similar-value transfers - repeated transaction structures - high
fan-in/fan-out

The system must label these as: - candidate pattern - potential
mixing-like structure - requires analyst review

## Important limitation

A detected structure is not proof of laundering or criminal activity.
