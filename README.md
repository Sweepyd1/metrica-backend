```mermaid
flowchart LR

  %% --- Zones as columns ---
  subgraph Z1[Client]
    direction TB
    U[User]
  end

  subgraph Z2[Frontend]
    direction TB
    FE[B Frontend UI]
    NOTE_FE[Rule: FE talks only to BE]
  end

  subgraph Z3[Edge]
    direction TB
    N[Nginx Reverse Proxy]
  end

  subgraph Z4[Backend]
    direction TB
    BE[A Backend API Core]

    subgraph MODS[Backend Modules]
      direction LR
      GM[C Groups Module]
      CM[D Calendar Module]
    end
  end

  subgraph Z5[Data]
    direction TB
    PG[(PostgreSQL)]
    RD[(Redis Optional)]
    NOTE_DB[Rule: schema migrations owned by A]
  end

  subgraph Z6[Ops]
    direction TB
    CI[CI CD]
  end

  %% --- Main request spine ---
  U --> FE -->|HTTP REST JSON| N -->|HTTP REST JSON| BE -->|SQL ORM| PG

  %% --- Internal / optional ---
  BE --> GM
  BE --> CM
  BE -.-> RD

  %% --- Notes (keep short links, near targets) ---
  NOTE_FE -.-> FE
  NOTE_DB -.-> PG

  %% --- CI CD influences (dashed) ---
  CI -.-> FE
  CI -.-> N
  CI -.-> BE

  %% --- Styling ---
  classDef fe fill:#E8F1FF,stroke:#2B6CB0,stroke-width:2px,color:#0B1F3A;
  classDef be fill:#E9FBEA,stroke:#2F855A,stroke-width:2px,color:#0B1F3A;
  classDef infra fill:#FFF7ED,stroke:#B45309,stroke-width:2px,color:#0B1F3A;
  classDef db fill:#FFF5F5,stroke:#C53030,stroke-width:2px,color:#0B1F3A;
  classDef note fill:#F7FAFC,stroke:#4A5568,stroke-width:1px,stroke-dasharray:4 3,color:#2D3748;

  class FE fe;
  class BE be;
  class N,CI infra;
  class PG,RD db;
  class NOTE_FE,NOTE_DB note;

  style Z1 fill:#FFFFFF,stroke:#CBD5E0,stroke-width:1px;
  style Z2 fill:#F6FAFF,stroke:#CBD5E0,stroke-width:1px;
  style Z3 fill:#FFF7ED,stroke:#CBD5E0,stroke-width:1px;
  style Z4 fill:#F0FFF4,stroke:#CBD5E0,stroke-width:1px;
  style Z5 fill:#FFF5F5,stroke:#CBD5E0,stroke-width:1px;
  style Z6 fill:#FFFBF0,stroke:#CBD5E0,stroke-width:1px;
