-- Tabla para tu menú (con la limpieza de categorías)
CREATE TABLE Productos (
    id_producto INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    precio DECIMAL(10, 2) NOT NULL,
    categoria VARCHAR(50),
    tipo_preparacion VARCHAR(20) DEFAULT 'Mostrador', -- 'Parrilla' o 'Mostrador'
    disponible BOOLEAN DEFAULT TRUE
);

-- Tabla principal de los pedidos que hacen los estudiantes
CREATE TABLE Pedidos (
    id_pedido INT AUTO_INCREMENT PRIMARY KEY,
    nombre_estudiante VARCHAR(100) NOT NULL,
    estado VARCHAR(30) DEFAULT 'En Cola', -- 'En Cola', 'Listo', 'Entregado'
    fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total DECIMAL(10, 2) NOT NULL
);

-- Tabla para saber qué pidió exactamente cada estudiante
CREATE TABLE Detalle_Pedidos (
    id_detalle INT AUTO_INCREMENT PRIMARY KEY,
    id_pedido INT,
    id_producto INT,
    cantidad INT NOT NULL,
    FOREIGN KEY (id_pedido) REFERENCES Pedidos(id_pedido),
    FOREIGN KEY (id_producto) REFERENCES Productos(id_producto)
);