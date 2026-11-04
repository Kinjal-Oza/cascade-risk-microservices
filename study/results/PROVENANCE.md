# Provenance and chronology (compiled 2026-11-03 for the EMSE revision)

## Chronology (all UTC)
| When (UTC) | Event | Evidence | Clock |
|---|---|---|---|
| 2026-10-28 21:46 | Campaign plan (Study 1) commit c0b9f4f | git, local repository (bundle published) | author machine (self-asserted) |
| 2026-10-28 21:50 | Scoring plan and method source commit 8a9f746 | git | self-asserted |
| 2026-10-28 21:52 | Method source (8 files) uploaded as Kaggle dataset kinjalvaishnav/crs-method-src | Kaggle file creationDate | **external (Kaggle server)** |
| 2026-10-28 21:53 | Alibaba re-analysis kernel run started (kinjalvaishnav/crs-alibaba-reanalysis) | Kaggle lastRunTime | **external** |
| 2026-10-28 22:11 | Green-light criteria commit 542dfa0 | git | self-asserted |
| 2026-10-28 23:24 | Deviation 1 (GitHub runners) commit 9af55e8 | git | self-asserted |
| 2026-10-29 01:46 | Harness commit e71c64d (crs-campaign) | git | self-asserted |
| 2026-10-29 01:49 – 04:53 | Study 1 runs (132 run start times t0) | run metadata | GitHub runner clocks |
| 2026-10-29 03:35 – 03:37 | Study 1 shard datasets crs-campaign-shard-0…11 | Kaggle lastUpdated | **external** |
| 2026-10-29 04:00 / 04:50 | Deviation 2 and addendum commits bf36280, 142c5f6 | git | self-asserted |
| 2026-10-29 04:32 – 05:02 | Re-run datasets crs-campaign-rerun-*, rerun2-* | Kaggle | **external** |
| 2026-10-29 05:41 | Scorer-as-run commit ddbdee9; results 1374b94 at 05:42 | git | self-asserted |
| 2026-10-29 06:23 | Campaign 2 plan commit 24a9454 | git | self-asserted |
| 2026-10-29 06:32 – 06:48 | Study 2 smoke datasets crs-c2smoke-* | Kaggle | **external** |
| 2026-11-01 21:54 – 21:55 | Study 2 smoke 2 datasets crs-c2smoke2-* | Kaggle | **external** |
| 2026-11-01 22:22 | Campaign 2 launch note 75a4b06 | git | self-asserted |
| 2026-11-01 22:26 – 23:48 | Study 2 runs (144 t0) | run metadata | runner clocks |
| 2026-11-01 23:36 – 23:59 | Study 2 shard datasets crs-c2-* | Kaggle | **external** |
| 2026-11-02 00:58 | Campaign 2 results and verdict commit 132e55b | git | self-asserted |

What this does and does not establish. The Kaggle timestamps are set by Kaggle's servers and show that the method source was fixed (and the Alibaba kernel started) before any Study 1 run, and that run data existed before the scoring commits. The plan documents themselves were committed to a local repository whose dates are set by the author's clock; they were not deposited with a third party (e.g. OSF) before the runs. The published git bundle preserves the commit graph and hashes but cannot prove the dates. We therefore describe the plans as "time-stamped in version control", not as externally registered.

## Container images
DeathStarBench commit 6ecb097 (2024-06-27); patch dsb.patch pins Jaeger to 1.57. Docker Hub tag metadata queried 2026-11-03:

| Image (tag in compose file) | Tag last pushed | amd64 / index digest now |
|---|---|---|
| deathstarbench/social-network-microservices:latest | 2024-06-27 | sha256:a845266e98ce… |
| deathstarbench/hotel-reservation:latest | 2024-06-27 | sha256:488d8980c81e… |
| jaegertracing/all-in-one:1.57 | 2024-05-02 | sha256:8f165334f418… |
| mongo:4.4.6 | 2021-07-14 | sha256:d9ddf3df3194… |
| mongo:5.0 | 2026-05-15 | sha256:41108d183e97… |
| yg397/openresty-thrift:xenial | 2021-04-26 | sha256:6c295fda3c2f… |
| yg397/media-frontend:xenial | 2019-05-06 | sha256:272049995f29… |
| hashicorp/consul:latest | 2026-10-22 | sha256:259fd02f2544… |
| memcached / memcached:latest | **2026-10-30** | sha256:aea0d81d101a… |
| redis (latest) | **2026-11-01 12:06** | sha256:de1068af6f55… |

Every application image and Jaeger was last pushed before Study 1, so their digests at run time equal the digests above. memcached:latest was re-pushed between the two studies and redis:latest about ten hours before Study 2; the two studies may therefore have used different memcached and redis builds, and the digests actually pulled were not logged. This is a stated limitation; the revised harness records `docker image inspect` digests per run.
