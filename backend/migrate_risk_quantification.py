import asyncio
import sys
sys.path.insert(0, '.')
from app.core.database import engine

async def migrate():
    async with engine.begin() as conn:
        # RiskItem 新增字段
        columns = [
            'ALTER TABLE risk_items ADD COLUMN IF NOT EXISTS clause_text TEXT',
            'ALTER TABLE risk_items ADD COLUMN IF NOT EXISTS clause_location VARCHAR(500)',
            'ALTER TABLE risk_items ADD COLUMN IF NOT EXISTS confidence FLOAT',
            'ALTER TABLE risk_items ADD COLUMN IF NOT EXISTS score_severity INTEGER',
            'ALTER TABLE risk_items ADD COLUMN IF NOT EXISTS score_likelihood INTEGER',
            'ALTER TABLE risk_items ADD COLUMN IF NOT EXISTS score_financial INTEGER',
            'ALTER TABLE risk_items ADD COLUMN IF NOT EXISTS score_responsibility INTEGER',
            'ALTER TABLE risk_items ADD COLUMN IF NOT EXISTS risk_score INTEGER',
            'ALTER TABLE risk_items ADD COLUMN IF NOT EXISTS potential_loss_min FLOAT',
            'ALTER TABLE risk_items ADD COLUMN IF NOT EXISTS potential_loss_max FLOAT',
            'ALTER TABLE risk_items ADD COLUMN IF NOT EXISTS loss_probability FLOAT',
            'ALTER TABLE risk_items ADD COLUMN IF NOT EXISTS expected_loss FLOAT',
            'ALTER TABLE risk_items ADD COLUMN IF NOT EXISTS quantification_detail JSONB',
        ]
        # RiskRule 新增字段
        rule_columns = [
            'ALTER TABLE risk_rules ADD COLUMN IF NOT EXISTS weight_severity FLOAT DEFAULT 0.40',
            'ALTER TABLE risk_rules ADD COLUMN IF NOT EXISTS weight_likelihood FLOAT DEFAULT 0.25',
            'ALTER TABLE risk_rules ADD COLUMN IF NOT EXISTS weight_financial FLOAT DEFAULT 0.20',
            'ALTER TABLE risk_rules ADD COLUMN IF NOT EXISTS weight_responsibility FLOAT DEFAULT 0.15',
        ]
        for sql in columns + rule_columns:
            try:
                await conn.execute(sql)
                print(f'OK: {sql}')
            except Exception as e:
                print(f'SKIP: {sql} -> {e}')
    print('Migration done!')

asyncio.run(migrate())
