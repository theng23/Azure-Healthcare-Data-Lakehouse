-- Run in the Azure SQL metadata database. New-install bootstrap, not a migration
-- for an existing ctrl schema. Compare with existing definitions before reuse.
IF SCHEMA_ID(N'ctrl') IS NULL EXEC(N'CREATE SCHEMA ctrl');
GO
IF OBJECT_ID(N'ctrl.table_config', N'U') IS NULL
BEGIN
    CREATE TABLE ctrl.table_config (
        table_id INT NOT NULL PRIMARY KEY,
        stage VARCHAR(30) NOT NULL,
        source_system VARCHAR(50) NULL,
        source_table_name SYSNAME NULL,
        source_path NVARCHAR(1000) NULL,
        source_file_format VARCHAR(20) NULL,
        bronze_table_name SYSNAME NULL,
        silver_table_name SYSNAME NULL,
        gold_table_name SYSNAME NULL,
        load_type VARCHAR(10) NOT NULL DEFAULT 'FULL',
        merge_keys NVARCHAR(500) NULL,
        watermark_column SYSNAME NULL,
        is_active BIT NOT NULL DEFAULT 0,
        CONSTRAINT CK_caresync_stage CHECK (stage IN ('SOURCE_TO_SILVER', 'SILVER_TO_GOLD')),
        CONSTRAINT CK_caresync_load_type CHECK (load_type IN ('FULL', 'APPEND', 'MERGE'))
    );
END;
GO
IF OBJECT_ID(N'ctrl.watermark', N'U') IS NULL
BEGIN
    CREATE TABLE ctrl.watermark (
        table_id INT NOT NULL PRIMARY KEY REFERENCES ctrl.table_config(table_id),
        watermark_value DATETIME2(7) NOT NULL
    );
END;
GO
IF OBJECT_ID(N'ctrl.audit_log', N'U') IS NULL
BEGIN
    CREATE TABLE ctrl.audit_log (
        audit_id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        adf_run_id VARCHAR(100) NOT NULL,
        table_id INT NOT NULL REFERENCES ctrl.table_config(table_id),
        stage VARCHAR(30) NOT NULL,
        status VARCHAR(20) NOT NULL,
        start_time DATETIME2(7) NOT NULL,
        end_time DATETIME2(7) NULL,
        records_written BIGINT NULL
    );
    CREATE INDEX IX_caresync_audit_run ON ctrl.audit_log(adf_run_id, table_id);
END;
GO
