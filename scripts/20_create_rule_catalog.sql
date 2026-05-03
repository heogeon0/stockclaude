-- 20_create_rule_catalog.sql
-- 라운드: 2026-05 weekly-review overhaul
-- rule_catalog DB single source-of-truth. 옛 한글 enum CHECK + INT[] 분산 통일.
-- LLM 이 register_rule MCP 로 새 룰 추가 가능 (학습→격상→카탈로그 자동 확장).
-- ====================================================================

CREATE TABLE IF NOT EXISTS rule_catalog (
  id            INT PRIMARY KEY,                          -- 1~15 fixed seed, 신규는 max+1
  enum_name     TEXT UNIQUE NOT NULL,                     -- 한글 슬러그 ('이벤트익절', '발굴사용자선택진입' 등)
  category      TEXT NOT NULL CHECK (category IN ('entry','exit','manage')),
  description   TEXT,                                     -- 룰 설명 (LLM 이 회고 시 인용)
  display_order INT,                                      -- 사용자 출력 정렬 (NULL 시 id 정렬)
  status        TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active','deprecated')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS trg_rule_catalog_updated ON rule_catalog;
CREATE TRIGGER trg_rule_catalog_updated
  BEFORE UPDATE ON rule_catalog
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- 활성 룰 조회 인덱스 (list_rule_catalog 최적화)
CREATE INDEX IF NOT EXISTS idx_rule_catalog_active
  ON rule_catalog (category, display_order)
  WHERE status = 'active';

-- ====================================================================
-- Seed 15 룰 (옛 trades.rule_category CHECK enum + AVGO _no_rule 후보 통합)
-- ====================================================================
INSERT INTO rule_catalog (id, enum_name, category, description, display_order) VALUES
  -- 진입 6
  (1,  '강매수시그널진입',    'entry',  '12 시그널 중 강매수 5+ + 일목/SEPA 정합 진입',                           1),
  (2,  '신고가돌파매수',      'entry',  '52주 신고가 돌파 + 거래량 1.5x 이상 진입',                              2),
  (3,  '가치신규진입',        'entry',  '저PBR (산업 평균 대비) + 컨센 상향 + 1Q 비트 같은 가치 thesis 진입',     3),
  (4,  'VCP_SEPA진입',       'entry',  'Minervini VCP 패턴 (수축률 8% 이내) + SEPA 정합 진입',                  4),
  (5,  '피라미딩D1안착',      'entry',  '피라미딩 D+1~2 안착 (전일 대비 +1% 이상) 확인 후 추가 진입',           5),
  (6,  '발굴사용자선택진입',  'entry',  'discover 결과에서 사용자 명시 선택한 종목 진입 (옛 _no_rule 통합)',    6),
  -- 청산 6
  (7,  '1차목표도달익절',    'exit',   '진입 시 설정한 1차 목표가 도달 시 부분 익절',                           7),
  (8,  '이벤트익절',         'exit',   '어닝 D-0/D+1 양방향 헤지 또는 호재 직후 부분 익절',                     8),
  (9,  '모멘텀꼴찌청산',      'exit',   '포트 내 모멘텀 z-score 꼴찌 종목 청산 (분산 헤지)',                     9),
  (10, '피라미딩실패컷',      'exit',   '피라미딩 D+1 안착 미달 시 추가분 환원 컷',                              10),
  (11, 'RSI과열청산',        'exit',   'RSI 80+ 극과열 + 매도 시그널 5+ 동반 시 부분/전량 청산',                11),
  (12, 'Defensive조기익절',   'exit',   'Defensive 등급 종목 +15% 도달 시 조기 익절',                            12),
  -- 관리 3
  (13, '집중도25%회수',      'manage', '단일 통화/섹터 비중 25%+ 도달 시 차주 강세 종목 부분 청산',              13),
  (14, 'ATR손절',           'manage', 'ATR 1.5~2x 손절선 이탈 시 전량 청산',                                   14),
  (15, '컨센하향청산',        'manage', '애널 컨센 (TP / rating) 하향 발생 시 청산 또는 비중 축소',              15)
ON CONFLICT (id) DO NOTHING;
