You are a senior Java QA/Dev engineer. Create a comprehensive test strategy and initial test scaffolding for this Java project.

## Confirm inputs
- Framework/runtime: (e.g., Spring Boot / Quarkus / Jakarta EE / plain Java)
- Build: Maven or Gradle
- Test libs available/allowed: JUnit 5, Mockito, Testcontainers, WireMock, RestAssured, Pact, Selenium/Playwright (pick Java bindings), JMH/Gatling, Jacoco
- External deps: databases, queues (Kafka/Rabbit), outbound HTTP APIs
- CI: GitHub Actions / GitLab CI / other
- Non-functional priorities: performance, security, reliability

## Goals
1) Propose a test strategy per layer (unit, integration, contract, E2E, non-functional) with priorities and coverage expectations (test pyramid).
2) Generate folder structure, example tests, and helper utilities to make tests easy to extend.
3) Add build/CI wiring for tests and coverage (Jacoco).
4) Keep tests deterministic and parallel-friendly.

## Work plan
1) Inventory & risk map
   - List modules/services, critical user journeys, data stores, outbound integrations, and risky areas.
2) Strategy draft
   - Define coverage per layer (unit vs integration vs contract vs E2E) and what each layer validates.
   - Define fixture strategy (builders/object mothers), fake data, and seeding.
3) Project structure & conventions
   - Standardize `src/test/java` layout, package mirrors, naming (`*Test`, `*IT`, `*ContractTest`, `*E2E`).
   - Add `src/test/resources` for fixtures and WireMock stubs.
4) Unit tests (fast, isolated)
   - Use JUnit 5 (`@Test`, `@ParameterizedTest`, dynamic tests where helpful).
   - Mock boundaries (Mockito), cover equivalence classes, boundaries, null/empty, and error paths.
   - Example: pure service/unit with assertions from `Assertions`.
5) Integration tests (real wiring)
   - Use Testcontainers for DB/queue; apply migrations (Flyway/Liquibase) before tests.
   - For Spring Boot: use test slices where possible; otherwise `@SpringBootTest` with containerized infra.
   - Verify persistence (CRUD + constraints) and configuration wiring.
6) Contract/API tests
   - Inbound API: RestAssured tests against app (local or containerized).
   - Outbound API: WireMock stubs; assert request shape + response handling.
   - Optional: Pact consumer/provider if contract testing is desired.
7) E2E/system tests
   - Choose Java-friendly tool (Selenium, Playwright for Java). Keep a minimal happy-path flow + key edge paths; keep counts low but valuable.
   - Seed data per test; avoid flaky time/network dependencies.
8) Non-functional
   - Performance: JMH microbench for hotspots OR Gatling for HTTP flows (separate module).
   - Reliability/resilience: add tests for timeouts/retries/circuit-breakers (unit/integration with fake clocks).
   - Security/smoke: authz/authn negative cases; basic input validation checks.
9) Test data & utilities
   - Add factory/builders for domain objects; deterministic defaults.
   - Reusable test extensions: `@TempDir` for filesystem, clock/UUID suppliers for determinism.
10) Build/CI wiring
    - Add Jacoco; fail CI on coverage regressions if desired.
    - Separate tasks: `test` (unit), `integrationTest`, `contractTest`, `e2eTest` where supported; wire profiles/Gradle source sets.
    - Parallelize where safe; mark non-parallel suites.
11) Outputs to produce
    - Written strategy (`TESTING.md`) summarizing layers, tools, and what each validates.
    - Scaffolding: sample tests per layer, helpers/builders, container config, WireMock/Pact samples.
    - Build config updates (Maven/Gradle) for plugins, source sets, Jacoco.
    - CI steps/jobs to run the suites (GitHub Actions / GitLab CI), with caches optional.

## Concrete snippets (use/adapt)
- JUnit 5 basics:
  ```java
  import static org.junit.jupiter.api.Assertions.assertEquals;
  import org.junit.jupiter.api.Test;
  class MyServiceTest {
    @Test void adds() { assertEquals(2, new Calculator().add(1,1)); }
  }
  ```
- Parameterized/dynamic tests for combinatorial coverage; use `@TempDir` for fs isolation.
- Testcontainers example:
  ```java
  @Testcontainers
  class UserRepoIT {
    @Container static PostgreSQLContainer<?> db = new PostgreSQLContainer<>("postgres:16");
    @BeforeAll static void init() { System.setProperty("DB_URL", db.getJdbcUrl()); }
  }
  ```
- WireMock for outbound HTTP:
  ```java
  @RegisterExtension static WireMockExtension wm = WireMockExtension.newInstance().options(wireMockConfig().dynamicPort()).build();
  ```
- RestAssured for inbound API checks; Pact for contracts if agreed.

## Deliverables
- `TESTING.md` with the agreed strategy and mapping from risks to tests.
- Updated `pom.xml`/`build.gradle` with test source sets, plugins (Surefire/Failsafe or Gradle equivalents), Jacoco.
- Test helpers/builders in `src/test/java/.../support/`.
- Example tests per layer: `*Test` (unit), `*IT` (integration), `*ContractTest` (API/contracts), `*E2E` (end-to-end).
- CI steps/jobs to run relevant suites.

Rules: prefer fast, deterministic tests; keep E2E sparse but meaningful; no flaky external calls; isolate time/randomness; fail fast on broken pipelines; document how to run each suite locally.
