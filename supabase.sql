-- Supabase SQL Editor 에 그대로 붙여 실행하십시오. (한 번만)
-- 하루짜리 검증 실험이라 anon 키로 읽기·쓰기를 허용한다.
-- 실험이 끝나면 정책을 조이거나 테이블을 지우면 된다.

create table if not exists articles (
  id              text primary key,           -- 원문 URL sha1 앞 12자
  brief_date      date        not null,       -- KST 기준 브리핑 날짜
  source          text        not null,
  source_priority int         not null default 1,
  title_en        text        not null,
  title_ko        text        not null,
  summary_ko      text[]      not null,       -- 정확히 3문장
  story_key       text        not null default '',
  url             text        not null,
  published       timestamptz not null,
  analysis        jsonb,                      -- 상세 화면 분석 리포트 (첫 열람 때 채워짐)
  created_at      timestamptz not null default now()
);

create index if not exists articles_brief_date_idx on articles (brief_date desc, published desc);

-- 반응 로그. 되돌리기·중복 제거는 하지 않는다(append-only). 집계할 때 세션 기준으로 추리면 된다.
-- kind = 'visit' 은 지표의 분모다. 목록 화면을 본 브라우저가 하루 한 번 남긴다.
create table if not exists reactions (
  id         bigint generated always as identity primary key,
  kind       text not null check (kind in ('article', 'revisit', 'missing', 'visit')),
  article_id text,                    -- kind = 'article' 일 때만
  value      text check (value in ('up', 'down')),
  note       text,                    -- kind = 'missing' 일 때 자유 입력
  session_id text not null,
  brief_date date not null,
  created_at timestamptz not null default now()
);

create index if not exists reactions_kind_idx on reactions (brief_date, kind);

alter table articles  enable row level security;
alter table reactions enable row level security;

drop policy if exists articles_read   on articles;
drop policy if exists articles_write  on articles;
drop policy if exists articles_update on articles;
drop policy if exists reactions_write on reactions;
drop policy if exists reactions_read  on reactions;

create policy articles_read   on articles  for select using (true);
create policy articles_write  on articles  for insert with check (true);
create policy articles_update on articles  for update using (true) with check (true);
create policy reactions_write on reactions for insert with check (true);
create policy reactions_read  on reactions for select using (true);

-- ── 지표 확인용 (SQL Editor 에서 그대로 실행) ─────────────────────────────
-- Primary: 방문 대비 '내일도 열어보겠다' 클릭 비율. 기준 60%.
--   select
--     count(distinct session_id) filter (where kind = 'visit')                      as 방문,
--     count(distinct session_id) filter (where kind = 'revisit' and value = 'up')   as 열어보겠다,
--     count(distinct session_id) filter (where kind = 'revisit' and value = 'down') as 아니다,
--     round(100.0 * count(distinct session_id) filter (where kind = 'revisit' and value = 'up')
--           / nullif(count(distinct session_id) filter (where kind = 'visit'), 0), 1) as 비율
--   from reactions where brief_date = current_date;
--
-- Supporting: 매체별 👍 분포
--   select a.source, r.value, count(distinct r.session_id)
--   from reactions r join articles a on a.id = r.article_id
--   where r.kind = 'article' and r.brief_date = current_date
--   group by 1, 2 order by 1;
--
-- Supporting: '빠진 소식' 자유 응답
--   select created_at, session_id, note from reactions
--   where kind = 'missing' and brief_date = current_date order by created_at;
