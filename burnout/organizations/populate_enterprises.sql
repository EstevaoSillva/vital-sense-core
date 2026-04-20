-- Script para popular o banco de dados com 10 empresas
-- Tabela: organizations_enterprise (baseada no modelo Enterprise em organizations/models.py)
-- Colunas mapeadas via db_column: 
-- id (BigInt), dt_created_at (Timestamptz), dt_modified_at (Timestamptz), cs_active (Bool), tx_name (Varchar), tx_code (Varchar), tx_kind (Varchar)

INSERT INTO organizations_enterprise (dt_created_at, dt_modified_at, cs_active, tx_name, tx_code, tx_kind) VALUES
(NOW(), NOW(), TRUE, 'Tech Innovations S.A.', 'TECH001', 'unit'),
(NOW(), NOW(), TRUE, 'Global Services Ltda', 'GLOB002', 'unit'),
(NOW(), NOW(), TRUE, 'Eco Solutions', 'ECO003', 'unit'),
(NOW(), NOW(), TRUE, 'Blue Sky Venture', 'BLUE004', 'unit'),
(NOW(), NOW(), TRUE, 'Nova Digital', 'NOVA005', 'unit'),
(NOW(), NOW(), TRUE, 'Alpha Industrial', 'ALPH006', 'unit'),
(NOW(), NOW(), TRUE, 'Summit Consulting', 'SUMM007', 'unit'),
(NOW(), NOW(), TRUE, 'Pioneer Logistics', 'PION008', 'unit'),
(NOW(), NOW(), TRUE, 'Stellar Systems', 'STEL009', 'unit'),
(NOW(), NOW(), TRUE, 'Zenith Healthcare', 'ZENI010', 'unit');
