"""
Test suite for EXTERNAL table import and export operations.
Tests various encodings, file types, and edge cases.
"""

import os
import stat
import tempfile
import threading
import time
import pytest
import nzpy


class TestExternalTableImport:
    """Test EXTERNAL table import operations with various encodings"""

    @pytest.fixture(autouse=True)
    def setup(self, con, cursor):
        """Setup test environment"""
        self.con = con
        self.cursor = cursor
        self.working_dir = tempfile.gettempdir()
        self.test_files = []

        yield

        # Cleanup test files
        for filepath in self.test_files:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass

    def _create_test_file(self, filename, content):
        """Helper to create test file and track for cleanup"""
        filepath = os.path.join(self.working_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(content)
        self.test_files.append(filepath)
        return filepath

    def test_import_latin1_encoding(self):
        """Test importing data with Latin-1 encoding"""
        # Create table
        self.cursor.execute("DROP TABLE test_import_latin1 IF EXISTS")
        self.cursor.execute("""
            CREATE TABLE test_import_latin1 (
                id INT,
                text_data VARCHAR(200)
            ) DISTRIBUTE ON RANDOM
        """)

        # Create test file with Latin-1 encoded data
        filepath = self._create_test_file(
            'test_import_latin1.csv',
            b'1,S\xfc\xdfes Caf\xe9\n2,\xc4pfel\n'
        )

        # Import data
        self.cursor.execute(f"""
            INSERT INTO test_import_latin1 SELECT *
            FROM EXTERNAL '{filepath}' SAMEAS test_import_latin1
            USING (
                ENCODING 'LATIN9'
                REMOTESOURCE 'python'
                DELIMITER ','
                LOGDIR '{self.working_dir}'
            )
        """)

        # Verify import
        self.cursor.execute("SELECT * FROM test_import_latin1 ORDER BY id")
        rows = self.cursor.fetchall()

        assert len(rows) == 2
        assert rows[0][0] == 1
        assert 'S' in rows[0][1] and 'Caf' in rows[0][1]
        assert rows[1][0] == 2
        assert 'pfel' in rows[1][1]

    def test_import_utf8_encoding(self):
        """Test importing data with UTF-8 encoding"""
        # Create table with NVARCHAR for UTF-8
        self.cursor.execute("DROP TABLE test_import_utf8 IF EXISTS")
        self.cursor.execute("""
            CREATE TABLE test_import_utf8 (
                id INT,
                text_data NVARCHAR(200)
            ) DISTRIBUTE ON RANDOM
        """)

        # Create test file with UTF-8 encoded data
        filepath = self._create_test_file(
            'test_import_utf8.csv',
            '1,Hello 世界\n2,Привет мир\n'.encode('utf-8')
        )

        # Import data
        self.cursor.execute(f"""
            INSERT INTO test_import_utf8 SELECT *
            FROM EXTERNAL '{filepath}' SAMEAS test_import_utf8
            USING (
                ENCODING 'UTF8'
                REMOTESOURCE 'python'
                DELIMITER ','
                LOGDIR '{self.working_dir}'
            )
        """)

        # Verify import
        self.cursor.execute("SELECT * FROM test_import_utf8 ORDER BY id")
        rows = self.cursor.fetchall()

        assert len(rows) == 2
        assert rows[0][0] == 1
        assert 'Hello' in rows[0][1]
        assert rows[1][0] == 2

    def test_import_internal_encoding(self):
        """Test importing data with internal encoding (mixed)"""
        # Create table
        self.cursor.execute("DROP TABLE test_import_internal IF EXISTS")
        self.cursor.execute("""
            CREATE TABLE test_import_internal (
                col1 VARCHAR(100),
                col2 NVARCHAR(100)
            ) DISTRIBUTE ON RANDOM
        """)

        # Create test file with mixed encoding
        filepath = self._create_test_file(
            'test_import_internal.csv',
            b'S\xfc\xdfes oder h\xe4ssliches Encoding?,S\xc3\xbc\xc3\x9fes oder h\xc3\xa4ssliches Encoding?'
        )

        # Import data
        self.cursor.execute(f"""
            INSERT INTO test_import_internal SELECT *
            FROM EXTERNAL '{filepath}' SAMEAS test_import_internal
            USING (
                ENCODING 'internal'
                REMOTESOURCE 'python'
                DELIMITER ','
                LOGDIR '{self.working_dir}'
            )
        """)

        # Verify import
        self.cursor.execute("SELECT * FROM test_import_internal")
        rows = self.cursor.fetchall()

        assert len(rows) == 1
        assert 'oder' in rows[0][0]
        assert 'oder' in rows[0][1]

    def test_import_ascii_encoding(self):
        """Test importing simple ASCII data"""
        # Create table
        self.cursor.execute("DROP TABLE test_import_ascii IF EXISTS")
        self.cursor.execute("""
            CREATE TABLE test_import_ascii (
                id INT,
                text_data VARCHAR(200)
            ) DISTRIBUTE ON RANDOM
        """)

        # Create test file with ASCII data
        filepath = self._create_test_file(
            'test_import_ascii.csv',
            b'1,Hello World\n2,Test Data\n3,Simple Text\n'
        )

        # Import data
        self.cursor.execute(f"""
            INSERT INTO test_import_ascii SELECT *
            FROM EXTERNAL '{filepath}' SAMEAS test_import_ascii
            USING (
                ENCODING 'LATIN9'
                REMOTESOURCE 'python'
                DELIMITER ','
                LOGDIR '{self.working_dir}'
            )
        """)

        # Verify import
        self.cursor.execute("SELECT COUNT(*) FROM test_import_ascii")
        count = self.cursor.fetchone()[0]

        assert count == 3

    def test_import_large_file(self):
        """Test importing large file with many rows"""
        # Create table
        self.cursor.execute("DROP TABLE test_import_large IF EXISTS")
        self.cursor.execute("""
            CREATE TABLE test_import_large (
                id INT,
                text_data NVARCHAR(200)
            ) DISTRIBUTE ON RANDOM
        """)

        # Create large test file
        content = []
        for i in range(1000):
            content.append(f'{i},Test data row {i}\n'.encode('utf-8'))

        filepath = self._create_test_file(
            'test_import_large.csv',
            b''.join(content)
        )

        # Import data
        self.cursor.execute(f"""
            INSERT INTO test_import_large SELECT *
            FROM EXTERNAL '{filepath}' SAMEAS test_import_large
            USING (
                ENCODING 'UTF8'
                REMOTESOURCE 'python'
                DELIMITER ','
                LOGDIR '{self.working_dir}'
            )
        """)

        # Verify import
        self.cursor.execute("SELECT COUNT(*) FROM test_import_large")
        count = self.cursor.fetchone()[0]

        assert count == 1000

    def test_import_empty_file(self):
        """Test importing empty file"""
        # Create table
        self.cursor.execute("DROP TABLE test_import_empty IF EXISTS")
        self.cursor.execute("""
            CREATE TABLE test_import_empty (
                id INT,
                text_data VARCHAR(200)
            ) DISTRIBUTE ON RANDOM
        """)
        
        # Create empty test file
        filepath = self._create_test_file('test_import_empty.csv', b'')
        
        # Import data (should succeed with 0 rows)
        self.cursor.execute(f"""
            INSERT INTO test_import_empty SELECT *
            FROM EXTERNAL '{filepath}' SAMEAS test_import_empty
            USING (
                ENCODING 'LATIN9'
                REMOTESOURCE 'python'
                DELIMITER ','
                LOGDIR '{self.working_dir}'
            )
        """)
        
        # Verify import
        self.cursor.execute("SELECT COUNT(*) FROM test_import_empty")
        count = self.cursor.fetchone()[0]
        
        assert count == 0


class TestExternalTableExport:
    """Test EXTERNAL table export operations with various encodings"""
    
    @pytest.fixture(autouse=True)
    def setup(self, con, cursor):
        """Setup test environment"""
        self.con = con
        self.cursor = cursor
        self.working_dir = tempfile.gettempdir()
        self.test_files = []
        
        yield
        
        # Cleanup test files
        for filepath in self.test_files:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
    
    def _track_file(self, filename):
        """Track file for cleanup"""
        filepath = os.path.join(self.working_dir, filename)
        self.test_files.append(filepath)
        return filepath
    
    def test_export_latin1_encoding(self):
        """Test exporting data with Latin-1 encoding"""
        # Create and populate table
        self.cursor.execute("DROP TABLE test_export_latin1 IF EXISTS")
        self.cursor.execute("""
            CREATE TABLE test_export_latin1 (
                id INT,
                text_data VARCHAR(200)
            ) DISTRIBUTE ON RANDOM
        """)
        self.cursor.execute("""
            INSERT INTO test_export_latin1 VALUES
            (1, 'Süßes Café')
        """)
        self.cursor.execute("""
            INSERT INTO test_export_latin1 VALUES
            (2, 'Äpfel')
        """)
        
        # Export data
        export_file = 'test_export_latin1.csv'
        filepath = self._track_file(export_file)
        
        self.cursor.execute(f"""
            CREATE EXTERNAL TABLE '{filepath}' USING (
                ENCODING 'LATIN9'
                REMOTESOURCE 'python'
                DELIMITER ','
                LOGDIR '{self.working_dir}'
            ) AS SELECT * FROM test_export_latin1
        """)
        
        # Verify export file exists and has content
        assert os.path.exists(filepath)
        with open(filepath, 'rb') as f:
            content = f.read()
            assert len(content) > 0
            assert b'Caf' in content or b'pfel' in content
    
    def test_export_utf8_encoding(self):
        """Test exporting data with UTF-8 encoding"""
        # Create and populate table with NVARCHAR
        self.cursor.execute("DROP TABLE test_export_utf8 IF EXISTS")
        self.cursor.execute("""
            CREATE TABLE test_export_utf8 (
                id INT,
                text_data NVARCHAR(200)
            ) DISTRIBUTE ON RANDOM
        """)
        self.cursor.execute("""
            INSERT INTO test_export_utf8 VALUES
            (1, 'Hello World')
        """)
        self.cursor.execute("""
            INSERT INTO test_export_utf8 VALUES
            (2, 'Test Data')
        """)
        
        # Export data
        export_file = 'test_export_utf8.csv'
        filepath = self._track_file(export_file)
        
        self.cursor.execute(f"""
            CREATE EXTERNAL TABLE '{filepath}' USING (
                ENCODING 'UTF8'
                REMOTESOURCE 'python'
                DELIMITER ','
                LOGDIR '{self.working_dir}'
            ) AS SELECT * FROM test_export_utf8
        """)
        
        # Verify export file exists and has content
        assert os.path.exists(filepath)
        with open(filepath, 'rb') as f:
            content = f.read()
            assert len(content) > 0
            assert b'Hello' in content or b'Test' in content
    
    def test_export_internal_encoding(self):
        """Test exporting data with internal encoding"""
        # Create and populate table
        self.cursor.execute("DROP TABLE test_export_internal IF EXISTS")
        self.cursor.execute("""
            CREATE TABLE test_export_internal (
                col1 VARCHAR(100),
                col2 NVARCHAR(100)
            ) DISTRIBUTE ON RANDOM
        """)
        self.cursor.execute("""
            INSERT INTO test_export_internal VALUES
            ('Test Data', 'Test Data')
        """)
        
        # Export data
        export_file = 'test_export_internal.csv'
        filepath = self._track_file(export_file)
        
        self.cursor.execute(f"""
            CREATE EXTERNAL TABLE '{filepath}' USING (
                ENCODING 'internal'
                REMOTESOURCE 'python'
                DELIMITER ','
                LOGDIR '{self.working_dir}'
            ) AS SELECT * FROM test_export_internal
        """)

        # Verify export file exists and has content
        assert os.path.exists(filepath)
        with open(filepath, 'rb') as f:
            content = f.read()
            assert len(content) > 0
            assert b'Test' in content

    def test_export_large_dataset(self):
        """Test exporting large dataset"""
        # Create and populate table with many rows
        self.cursor.execute("DROP TABLE test_export_large IF EXISTS")
        self.cursor.execute("""
            CREATE TABLE test_export_large (
                id INT,
                text_data VARCHAR(200)
            ) DISTRIBUTE ON RANDOM
        """)

        # Insert multiple rows
        for i in range(100):
            self.cursor.execute(
                f"INSERT INTO test_export_large VALUES ({i}, 'Test data row {i}')"
            )

        # Export data
        export_file = 'test_export_large.csv'
        filepath = self._track_file(export_file)

        self.cursor.execute(f"""
            CREATE EXTERNAL TABLE '{filepath}' USING (
                ENCODING 'LATIN9'
                REMOTESOURCE 'python'
                DELIMITER ','
                LOGDIR '{self.working_dir}'
            ) AS SELECT * FROM test_export_large
        """)

        # Verify export file exists and has substantial content
        assert os.path.exists(filepath)
        file_size = os.path.getsize(filepath)
        assert file_size > 1000  # Should be at least 1KB for 100 rows

    def test_export_empty_table(self):
        """Test exporting empty table"""
        # Create empty table
        self.cursor.execute("DROP TABLE test_export_empty IF EXISTS")
        self.cursor.execute("""
            CREATE TABLE test_export_empty (
                id INT,
                text_data VARCHAR(200)
            ) DISTRIBUTE ON RANDOM
        """)

        # Export data
        export_file = 'test_export_empty.csv'
        filepath = self._track_file(export_file)

        self.cursor.execute(f"""
            CREATE EXTERNAL TABLE '{filepath}' USING (
                ENCODING 'LATIN9'
                REMOTESOURCE 'python'
                DELIMITER ','
                LOGDIR '{self.working_dir}'
            ) AS SELECT * FROM test_export_empty
        """)

        # Verify export file exists (may be empty or have minimal content)
        assert os.path.exists(filepath)


class TestExternalTableFIFO:
    """Test EXTERNAL table operations with FIFOs (named pipes)"""

    @pytest.fixture(autouse=True)
    def setup(self, con, cursor):
        """Setup test environment"""
        self.con = con
        self.cursor = cursor
        self.working_dir = tempfile.gettempdir()
        self.test_fifos = []

        yield

        # Cleanup FIFOs
        for fifo_path in self.test_fifos:
            if os.path.exists(fifo_path):
                try:
                    os.remove(fifo_path)
                except Exception:
                    pass

    @pytest.mark.skipif(not hasattr(os, 'mkfifo'), 
                       reason="FIFOs not supported on this platform")
    def test_import_from_fifo(self):
        """Test importing data from a FIFO (named pipe)"""
        fifo_path = os.path.join(self.working_dir, 'test_import.fifo')
        self.test_fifos.append(fifo_path)

        # Create FIFO
        if os.path.exists(fifo_path):
            os.remove(fifo_path)
        os.mkfifo(fifo_path)

        # Create table
        self.cursor.execute("DROP TABLE test_fifo_import IF EXISTS")
        self.cursor.execute("""
            CREATE TABLE test_fifo_import (
                id INT,
                text_data VARCHAR(200)
            ) DISTRIBUTE ON RANDOM
        """)
        
        # Function to write data to FIFO
        def write_to_fifo():
            time.sleep(1)  # Give import time to start
            with open(fifo_path, 'wb') as f:
                f.write(b'1,FIFO Test Data\n')
                f.write(b'2,Streaming Import\n')
        
        # Start writer thread
        writer_thread = threading.Thread(target=write_to_fifo)
        writer_thread.start()
        
        # Import from FIFO
        self.cursor.execute(f"""
            INSERT INTO test_fifo_import SELECT *
            FROM EXTERNAL '{fifo_path}' SAMEAS test_fifo_import
            USING (
                ENCODING 'LATIN9'
                REMOTESOURCE 'python'
                DELIMITER ','
                LOGDIR '{self.working_dir}'
            )
        """)
        
        # Wait for writer
        writer_thread.join()
        
        # Verify import
        self.cursor.execute("SELECT COUNT(*) FROM test_fifo_import")
        count = self.cursor.fetchone()[0]
        
        assert count == 2
    
    @pytest.mark.skipif(not hasattr(os, 'mkfifo'),
                       reason="FIFOs not supported on this platform")
    def test_export_to_fifo(self):
        """Test exporting data to a FIFO (named pipe)"""
        fifo_path = os.path.join(self.working_dir, 'test_export.fifo')
        self.test_fifos.append(fifo_path)
        
        # Create FIFO
        if os.path.exists(fifo_path):
            os.remove(fifo_path)
        os.mkfifo(fifo_path)

        # Create and populate table
        self.cursor.execute("DROP TABLE test_fifo_export IF EXISTS")
        self.cursor.execute("""
            CREATE TABLE test_fifo_export (
                id INT,
                text_data VARCHAR(200)
            ) DISTRIBUTE ON RANDOM
        """)
        self.cursor.execute("""
            INSERT INTO test_fifo_export VALUES
            (1, 'FIFO Export Test')
        """)
        self.cursor.execute("""
            INSERT INTO test_fifo_export VALUES
            (2, 'Streaming Output')
        """)

        # Function to read data from FIFO
        exported_data = []
        def read_from_fifo():
            time.sleep(1)  # Give export time to start
            with open(fifo_path, 'rb') as f:
                data = f.read()
                exported_data.append(data)

        # Start reader thread
        reader_thread = threading.Thread(target=read_from_fifo)
        reader_thread.start()

        # Export to FIFO
        self.cursor.execute(f"""
            CREATE EXTERNAL TABLE '{fifo_path}' USING (
                ENCODING 'LATIN9'
                REMOTESOURCE 'python'
                DELIMITER ','
                LOGDIR '{self.working_dir}'
            ) AS SELECT * FROM test_fifo_export
        """)

        # Wait for reader
        reader_thread.join()

        # Verify export
        assert len(exported_data) > 0
        assert len(exported_data[0]) > 0


class TestExternalTableEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.fixture(autouse=True)
    def setup(self, con, cursor):
        """Setup test environment"""
        self.con = con
        self.cursor = cursor
        self.working_dir = tempfile.gettempdir()
        self.test_files = []
        
        yield
        
        # Cleanup
        for filepath in self.test_files:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
    
    def test_import_file_with_no_trailing_newline(self):
        """Test importing file without trailing newline"""
        # Create table
        self.cursor.execute("DROP TABLE test_no_newline IF EXISTS")
        self.cursor.execute("""
            CREATE TABLE test_no_newline (
                id INT,
                text_data VARCHAR(200)
            ) DISTRIBUTE ON RANDOM
        """)
        
        # Create test file without trailing newline
        filepath = os.path.join(self.working_dir, 'test_no_newline.csv')
        self.test_files.append(filepath)
        with open(filepath, 'wb') as f:
            f.write(b'1,Test Data')  # No \n at end
        
        # Import should still work
        self.cursor.execute(f"""
            INSERT INTO test_no_newline SELECT *
            FROM EXTERNAL '{filepath}' SAMEAS test_no_newline
            USING (
                ENCODING 'LATIN9'
                REMOTESOURCE 'python'
                DELIMITER ','
                LOGDIR '{self.working_dir}'
            )
        """)
        
        # Verify import
        self.cursor.execute("SELECT COUNT(*) FROM test_no_newline")
        count = self.cursor.fetchone()[0]
        
        assert count == 1
    
    def test_import_file_not_found(self):
        """Test importing from non-existent file"""
        # Create table
        self.cursor.execute("DROP TABLE test_not_found IF EXISTS")
        self.cursor.execute("""
            CREATE TABLE test_not_found (
                id INT,
                text_data VARCHAR(200)
            ) DISTRIBUTE ON RANDOM
        """)
        
        # Try to import from non-existent file
        non_existent = os.path.join(self.working_dir, 'does_not_exist.csv')
        
        # Should raise FileNotFoundError (which is what our fix does)
        with pytest.raises((FileNotFoundError, nzpy.Error)):
            self.cursor.execute(f"""
                INSERT INTO test_not_found SELECT *
                FROM EXTERNAL '{non_existent}' SAMEAS test_not_found
                USING (
                    ENCODING 'LATIN9'
                    REMOTESOURCE 'python'
                    DELIMITER ','
                    LOGDIR '{self.working_dir}'
                )
            """)
