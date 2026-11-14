-- Catálogos base. Idempotente: se puede ejecutar varias veces.

INSERT INTO crop (code, name) VALUES
    ('MAIZ',   'Maíz'),
    ('FRIJOL', 'Frijol')
ON CONFLICT (code) DO NOTHING;

INSERT INTO strategy (code, name, focus, description) VALUES
    ('E1', 'Línea base tradicional',  'Práctica actual del productor.',
          'PENDIENTE: definir rotación y prácticas (README, sección 5.1).'),
    ('E2', 'Conservación hídrica',    'Maximizar el aprovechamiento y la retención de agua.',
          'PENDIENTE: definir rotación y prácticas (README, sección 5.1).'),
    ('E3', 'Regeneración de suelos',  'Recuperar materia orgánica y estructura del suelo.',
          'PENDIENTE: definir rotación y prácticas (README, sección 5.1).')
ON CONFLICT (code) DO NOTHING;

-- Las regiones análogas (analog_region) se cargan en una semilla aparte
-- cuando el registro de la sección 2.2 del README esté completo.
