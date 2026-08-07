# Security Review 0001: Repository Foundation

Status: Accepted for repository genesis.

## Surface

This public repository currently contains documentation and coordination
metadata only. It has no package execution, network listener, authentication,
cryptography, provider access, secret resolution, Docker behavior, image
publication, or application mutation.

## Prohibited Material

Repository files must not contain credentials, private keys, secret values,
compact grants, signatures, private endpoints, package tokens, provider
authority, or workflow secrets. Public verification keys are integrity-sensitive
future configuration and are not introduced by genesis.

## Dependency Direction

The future SDK may consume pinned pure core contracts. It must not depend on
operations stores, cpk-server, interpreters, server products, Postgres,
Cloudflare, Docker SDK, or FastAPI in the base install.

## Residual Risk

The durable risk at this stage is repository-policy drift: an implementation or
credential-bearing workflow could be added before its owning issue and review.
Issue OpenJ92/control-plane-kit#1479 must install the repository policy and
Docker-first package gate before SDK behavior begins.
