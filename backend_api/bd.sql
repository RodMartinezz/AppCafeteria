-- 1. Tabla de Productos mejorada
CREATE TABLE Productos (
    id_producto INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    precio DECIMAL(10, 2) NOT NULL,
    -- Agregamos ENUM para asegurar que solo existan estas dos categorías
    categoria ENUM('Comida', 'Bebida') NOT NULL, 
    tipo_preparacion ENUM('Parrilla', 'Mostrador') DEFAULT 'Mostrador',
    -- Para apagar productos si se acaban en el día
    disponible BOOLEAN DEFAULT TRUE,
    -- Índice para que el filtrado por Comida/Bebida en la app sea instantáneo
    INDEX (categoria)
);

-- 2. Tabla de Pedidos con estados controlados
CREATE TABLE Pedidos (
    id_pedido INT AUTO_INCREMENT PRIMARY KEY,
    nombre_estudiante VARCHAR(100) NOT NULL,
    -- Usamos ENUM para evitar errores de escritura en los estados
    estado ENUM('En Cola', 'Preparando', 'Listo', 'Entregado') DEFAULT 'En Cola',
    fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total DECIMAL(10, 2) NOT NULL,
    -- Índice para la pantalla de los cocineros (KDS)
    INDEX (estado)
);

-- 3. Tabla de Detalle con campo de notas
CREATE TABLE Detalle_Pedidos (
    id_detalle INT AUTO_INCREMENT PRIMARY KEY,
    id_pedido INT,
    id_producto INT,
    cantidad INT NOT NULL,
    -- Campo extra para personalización (ej. "sin cebolla", "con azúcar")
    notas VARCHAR(255),
    FOREIGN KEY (id_pedido) REFERENCES Pedidos(id_pedido) ON DELETE CASCADE,
    FOREIGN KEY (id_producto) REFERENCES Productos(id_producto)
);