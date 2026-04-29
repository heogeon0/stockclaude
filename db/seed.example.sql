-- =====================================================================
-- 최소 데모 시드 (public 레포용)
-- =====================================================================
--
-- 이 파일은 빈 DB 위에 데모 사용자 1명 + 기본 산업 분류만 넣는다.
-- 실 매매 데이터는 포함하지 않는다.
--
-- 실행:
--   psql $DATABASE_URL < db/schema.sql       # 스키마 먼저
--   psql $DATABASE_URL < db/seed.example.sql # 그 다음 이 파일
--
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. 데모 유저
-- ---------------------------------------------------------------------
INSERT INTO users (id, email)
VALUES ('00000000-0000-0000-0000-000000000000', 'demo@example.com')
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------
-- 2. 기본 산업 분류 (KR)
--    공개 정보 — KRX 업종분류 기준 일부만
-- ---------------------------------------------------------------------
INSERT INTO industries (code, market, name, name_en) VALUES
  ('semiconductor-kr', 'kr', '반도체',     'Semiconductors'),
  ('battery-kr',       'kr', '2차전지',    'Batteries'),
  ('biotech-kr',       'kr', '바이오',     'Biotech'),
  ('finance-kr',       'kr', '금융',       'Financials'),
  ('it-kr',            'kr', 'IT서비스',   'IT Services'),
  ('automotive-kr',    'kr', '자동차',     'Automotive'),
  ('shipbuilding-kr',  'kr', '조선',       'Shipbuilding'),
  ('chemicals-kr',     'kr', '화학',       'Chemicals')
ON CONFLICT (code) DO NOTHING;

-- ---------------------------------------------------------------------
-- 3. 기본 산업 분류 (US)
-- ---------------------------------------------------------------------
INSERT INTO industries (code, market, name, name_en) VALUES
  ('us-semiconductor', 'us', 'Semiconductors',          'Semiconductors'),
  ('us-software',      'us', 'Software',                'Software'),
  ('us-financials',    'us', 'Financials',              'Financials'),
  ('us-healthcare',    'us', 'Healthcare',              'Healthcare'),
  ('us-energy',        'us', 'Energy',                  'Energy'),
  ('us-consumer',      'us', 'Consumer Discretionary',  'Consumer Discretionary'),
  ('us-industrials',   'us', 'Industrials',             'Industrials')
ON CONFLICT (code) DO NOTHING;

-- ---------------------------------------------------------------------
-- 4. 데모 종목 (시총 상위, 공개 정보)
-- ---------------------------------------------------------------------
INSERT INTO stocks (code, name, market, currency, industry_code) VALUES
  ('005930', '삼성전자',     'kr', 'KRW', 'semiconductor-kr'),
  ('000660', 'SK하이닉스',   'kr', 'KRW', 'semiconductor-kr'),
  ('373220', 'LG에너지솔루션','kr', 'KRW', 'battery-kr'),
  ('NVDA',   'NVIDIA',      'us', 'USD', 'us-semiconductor'),
  ('GOOGL',  'Alphabet',    'us', 'USD', 'us-software')
ON CONFLICT (code) DO NOTHING;

COMMIT;
