import sqlite3

# Conectar a la base de datos (o crearla si no existe)
conn = sqlite3.connect('health_data.db')
cursor = conn.cursor()

# Crear la tabla 'casos_covid'
cursor.execute('''
CREATE TABLE IF NOT EXISTS casos_covid (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT,
    ubicacion_id INTEGER,
    casos_confirmados INTEGER,
    muertes INTEGER,
    casos_activos INTEGER,
    casos_recuperados INTEGER,
    FOREIGN KEY (ubicacion_id) REFERENCES ubicaciones(id)
)
''')

# Crear la tabla 'hospitalizaciones'
cursor.execute('''
CREATE TABLE IF NOT EXISTS hospitalizaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ubicacion_id INTEGER,
    fecha TEXT,
    camas_disponibles INTEGER,
    camas_ocupadas INTEGER,
    FOREIGN KEY (ubicacion_id) REFERENCES ubicaciones(id)
)
''')

# Crear la tabla 'vacunaciones'
cursor.execute('''
CREATE TABLE IF NOT EXISTS vacunaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ubicacion_id INTEGER,
    fecha TEXT,
    personas_vacunadas INTEGER,
    dosis_administradas INTEGER,
    tipo_vacuna TEXT,
    FOREIGN KEY (ubicacion_id) REFERENCES ubicaciones(id)
)
''')

# Crear la tabla 'pruebas'
cursor.execute('''
CREATE TABLE IF NOT EXISTS pruebas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ubicacion_id INTEGER,
    fecha TEXT,
    total_pruebas INTEGER,
    tipo_prueba TEXT,
    pruebas_positivas INTEGER,
    FOREIGN KEY (ubicacion_id) REFERENCES ubicaciones(id)
)
''')

# Crear la tabla 'ubicaciones'
cursor.execute('''
CREATE TABLE IF NOT EXISTS ubicaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pais TEXT,
    ciudad TEXT
)
''')

# Insertar datos de ejemplo en 'ubicaciones'
cursor.executemany('''
INSERT INTO ubicaciones (pais, ciudad)
VALUES (?, ?)
''', [
    ('México', 'Ciudad de México'),
    ('México', 'Guadalajara'),
    ('Estados Unidos', 'Nueva York'),
    ('Estados Unidos', 'Los Ángeles')
])

# Insertar datos de ejemplo en 'casos_covid'
cursor.executemany('''
INSERT INTO casos_covid (fecha, ubicacion_id, casos_confirmados, muertes, casos_activos, casos_recuperados)
VALUES (?, ?, ?, ?, ?, ?)
''', [
    ('2023-01-01', 1, 150, 5, 80, 65),
    ('2023-02-01', 2, 200, 8, 90, 95),
    ('2023-01-01', 3, 300, 10, 180, 110),
    ('2023-02-01', 4, 400, 15, 220, 165)
])

# Insertar datos de ejemplo en 'hospitalizaciones'
cursor.executemany('''
INSERT INTO hospitalizaciones (ubicacion_id, fecha, camas_disponibles, camas_ocupadas)
VALUES (?, ?, ?, ?)
''', [
    (1, '2023-01-01', 100, 30),
    (2, '2023-02-01', 120, 45),
    (3, '2023-01-01', 80, 50),
    (4, '2023-02-01', 90, 60)
])

# Insertar datos de ejemplo en 'vacunaciones'
cursor.executemany('''
INSERT INTO vacunaciones (ubicacion_id, fecha, personas_vacunadas, dosis_administradas, tipo_vacuna)
VALUES (?, ?, ?, ?, ?)
''', [
    (1, '2023-01-01', 1000, 1500, 'Pfizer'),
    (2, '2023-02-01', 800, 1200, 'Moderna'),
    (3, '2023-01-01', 1500, 2000, 'Johnson'),
    (4, '2023-02-01', 1100, 1700, 'AstraZeneca')
])

# Insertar datos de ejemplo en 'pruebas'
cursor.executemany('''
INSERT INTO pruebas (ubicacion_id, fecha, total_pruebas, tipo_prueba, pruebas_positivas)
VALUES (?, ?, ?, ?, ?)
''', [
    (1, '2023-01-01', 500, 'PCR', 150),
    (2, '2023-02-01', 600, 'Antígenos', 200),
    (3, '2023-01-01', 450, 'PCR', 120),
    (4, '2023-02-01', 550, 'Antígenos', 180)
])

# Confirmar los cambios
conn.commit()

# Cerrar la conexión
conn.close()

print("Base de datos creada y datos insertados correctamente.")
