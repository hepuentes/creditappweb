from datetime import datetime
from flask_login import UserMixin
from . import db
from werkzeug.security import generate_password_hash, check_password_hash
import logging

from app import db, login_manager, bcrypt

# Configurar logging para el módulo
logger = logging.getLogger(__name__)


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


class Usuario(db.Model, UserMixin):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default="usuario")
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    activo = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        """Establece la contraseña del usuario de forma segura"""
        from app import bcrypt

        self.password = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        """Verifica si la contraseña proporcionada coincide con la almacenada"""
        from app import bcrypt

        return bcrypt.check_password_hash(self.password, password)

    def is_authenticated(self):
        return True

    def is_active(self):
        return self.activo

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    def is_admin(self):
        return self.rol == "administrador"

    def is_vendedor(self):
        return self.rol == "vendedor"

    def is_cobrador(self):
        return self.rol == "cobrador"


class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    cedula = db.Column(db.String(20), unique=True, nullable=False)
    telefono = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    direccion = db.Column(db.String(200), nullable=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    ventas = db.relationship(
        "Venta", back_populates="cliente", lazy=True, cascade="all, delete-orphan"
    )
    creditos = db.relationship(
        "Credito", backref="cliente", lazy=True, cascade="all, delete-orphan"
    )

    def saldo_pendiente(self):
        return sum(v.saldo_pendiente for v in self.ventas if v.tipo == "credito")


class Venta(db.Model):
    __tablename__ = "ventas"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    vendedor_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    total = db.Column(db.Integer, nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # 'contado' o 'credito'
    saldo_pendiente = db.Column(db.Integer, nullable=True)  # sólo para crédito
    estado = db.Column(
        db.String(20), nullable=False, default="pendiente"
    )  # 'pendiente' o 'pagado'
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    # CAMPOS PARA TRANSFERENCIAS - CORREGIDOS
    vendedor_original_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=True
    )  # Vendedor que originalmente hizo la venta
    usuario_actual_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=True
    )  # Usuario que actualmente gestiona la venta
    transferida = db.Column(
        db.Boolean, default=False, nullable=False
    )  # Si la venta ha sido transferida
    fecha_transferencia = db.Column(db.DateTime, nullable=True)  # Cuándo se transfirió

    # Relaciones existentes
    cliente = db.relationship("Cliente", back_populates="ventas")
    vendedor = db.relationship("Usuario", foreign_keys=[vendedor_id], backref="ventas")
    detalles = db.relationship(
        "DetalleVenta", backref="venta", lazy=True, cascade="all, delete-orphan"
    )
    abonos = db.relationship(
        "Abono", back_populates="venta", foreign_keys="Abono.venta_id", lazy=True
    )

    # RELACIONES PARA TRANSFERENCIAS - CORREGIDAS
    vendedor_original = db.relationship(
        "Usuario", foreign_keys=[vendedor_original_id], backref="ventas_originales"
    )
    usuario_actual = db.relationship(
        "Usuario", foreign_keys=[usuario_actual_id], backref="ventas_gestionadas"
    )

    def usuario_gestor(self):
        """
        Retorna el usuario que actualmente gestiona esta venta
        VERSIÓN COMPLETAMENTE CORREGIDA con mejor manejo de errores
        """
        try:
            # Caso 1: Venta transferida con usuario actual válido
            if self.transferida and self.usuario_actual_id:
                try:
                    usuario_actual = Usuario.query.get(self.usuario_actual_id)
                    if usuario_actual and usuario_actual.activo:
                        logger.debug(
                            f"Venta {self.id}: Gestor = usuario actual transferido {usuario_actual.nombre}"
                        )
                        return usuario_actual
                    else:
                        logger.warning(
                            f"Venta {self.id}: Usuario actual {self.usuario_actual_id} no válido o inactivo"
                        )
                        # Continuar al siguiente caso
                except Exception as e:
                    logger.error(
                        f"Error obteniendo usuario_actual para venta {self.id}: {e}"
                    )
                    # Continuar al siguiente caso

            # Caso 2: Usar vendedor original (ya sea transferida o no)
            try:
                vendedor = Usuario.query.get(self.vendedor_id)
                if vendedor and vendedor.activo:
                    logger.debug(
                        f"Venta {self.id}: Gestor = vendedor original {vendedor.nombre}"
                    )
                    return vendedor
                else:
                    logger.warning(
                        f"Venta {self.id}: Vendedor original {self.vendedor_id} no válido o inactivo"
                    )
            except Exception as e:
                logger.error(
                    f"Error obteniendo vendedor original para venta {self.id}: {e}"
                )

            # Caso 3: Fallback - buscar cualquier administrador activo
            try:
                admin_fallback = Usuario.query.filter_by(
                    rol="administrador", activo=True
                ).first()
                if admin_fallback:
                    logger.warning(
                        f"Venta {self.id}: Usando admin fallback {admin_fallback.nombre}"
                    )
                    return admin_fallback
            except Exception as e:
                logger.error(f"Error buscando admin fallback para venta {self.id}: {e}")

            # Caso 4: Último recurso - cualquier usuario activo
            try:
                usuario_fallback = Usuario.query.filter_by(activo=True).first()
                if usuario_fallback:
                    logger.error(
                        f"Venta {self.id}: Usando usuario fallback {usuario_fallback.nombre}"
                    )
                    return usuario_fallback
            except Exception as e:
                logger.error(
                    f"Error buscando usuario fallback para venta {self.id}: {e}"
                )

            # Si llegamos aquí, hay un problema grave
            logger.critical(
                f"Venta {self.id}: No se pudo determinar ningún gestor válido"
            )
            raise ValueError(
                f"No se puede determinar gestor para venta {self.id} - no hay usuarios activos"
            )

        except Exception as e:
            logger.critical(
                f"Error crítico en usuario_gestor para venta {self.id}: {e}"
            )
            raise

    def puede_gestionar(self, usuario):
        """
        Verifica si un usuario puede gestionar esta venta
        VERSIÓN CORREGIDA con mejor lógica
        """
        try:
            if not usuario or not usuario.activo:
                return False

            # Los administradores pueden gestionar cualquier venta
            if usuario.is_admin():
                return True

            # Si la venta está transferida
            if self.transferida:
                # Solo el usuario actual asignado puede gestionarla
                if self.usuario_actual_id:
                    return self.usuario_actual_id == usuario.id
                else:
                    # Si está marcada como transferida pero no tiene usuario_actual_id,
                    # permitir al vendedor original (caso de transferencia incompleta)
                    logger.warning(f"Venta {self.id} transferida sin usuario_actual_id")
                    return self.vendedor_id == usuario.id
            else:
                # Si no está transferida, solo el vendedor original puede gestionarla
                return self.vendedor_id == usuario.id

        except Exception as e:
            logger.error(
                f"Error en puede_gestionar para venta {self.id}, usuario {usuario.id if usuario else 'None'}: {e}"
            )
            return False

    def obtener_gestor_seguro(self):
        """
        Obtiene el gestor de forma segura, con información adicional de estado
        VERSIÓN COMPLETAMENTE CORREGIDA
        """
        try:
            # Obtener el gestor actual usando el método usuario_gestor
            gestor = self.usuario_gestor()

            if not gestor:
                logger.error(f"No se pudo obtener gestor para venta {self.id}")
                return {
                    "usuario": None,
                    "es_transferida": self.transferida,
                    "es_original": not self.transferida,
                    "vendedor_original": None,
                    "error": "No se pudo determinar el gestor de esta venta",
                }

            # Obtener vendedor original de forma segura
            vendedor_original = None
            if self.transferida and self.vendedor_original_id:
                try:
                    vendedor_original = Usuario.query.get(self.vendedor_original_id)
                except Exception as e:
                    logger.warning(
                        f"Error obteniendo vendedor original para venta {self.id}: {e}"
                    )
                    # Si no se puede obtener por vendedor_original_id, usar vendedor_id
                    try:
                        vendedor_original = Usuario.query.get(self.vendedor_id)
                    except Exception as e2:
                        logger.error(
                            f"Error obteniendo vendedor por vendedor_id para venta {self.id}: {e2}"
                        )

            return {
                "usuario": gestor,
                "es_transferida": self.transferida,
                "es_original": not self.transferida,
                "vendedor_original": vendedor_original,
                "gestor_id": gestor.id,
                "gestor_nombre": gestor.nombre,
                "gestor_rol": gestor.rol,
            }

        except Exception as e:
            logger.error(
                f"Error crítico en obtener_gestor_seguro para venta {self.id}: {e}"
            )

            # Fallback: intentar obtener al menos el vendedor original
            fallback_usuario = None
            try:
                fallback_usuario = Usuario.query.get(self.vendedor_id)
            except:
                pass

            return {
                "usuario": fallback_usuario,
                "es_transferida": self.transferida,
                "es_original": not self.transferida,
                "vendedor_original": fallback_usuario,
                "error": f"Error crítico: {str(e)}",
            }

    def debug_info(self):
        """
        Información de debug para la venta
        """
        try:
            gestor_info = self.obtener_gestor_seguro()
            return {
                "venta_id": self.id,
                "transferida": self.transferida,
                "vendedor_id": self.vendedor_id,
                "vendedor_original_id": self.vendedor_original_id,
                "usuario_actual_id": self.usuario_actual_id,
                "gestor_actual": gestor_info.get("gestor_nombre", "No determinado"),
                "tiene_error": "error" in gestor_info,
            }
        except Exception as e:
            return {"venta_id": self.id, "error": str(e)}

    @property
    def estado_transferencia(self):
        """Retorna el estado de transferencia de forma legible"""
        if not self.transferida:
            return "Original"
        elif self.usuario_actual_id:
            return "Transferida"
        else:
            return "Transferencia incompleta"

    def __repr__(self):
        return f"<Venta #{self.id} Cliente:{self.cliente_id} Total:{self.total} Transferida:{self.transferida}>"


class Credito(db.Model):
    __tablename__ = "creditos"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    monto = db.Column(db.Integer, nullable=False)
    plazo = db.Column(db.Integer, nullable=False)
    tasa = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    # relación con abonos
    abonos = db.relationship(
        "Abono", backref="credito", lazy=True, cascade="all, delete-orphan"
    )

    @property
    def saldo_pendiente(self):
        pagado = sum(a.monto for a in self.abonos)
        return self.monto - pagado

    def __repr__(self):
        return f"<Credito #{self.id} Cliente:{self.cliente_id} Monto:{self.monto}>"


class Abono(db.Model):
    __tablename__ = "abonos"

    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey("ventas.id"), nullable=True)
    credito_id = db.Column(db.Integer, db.ForeignKey("creditos.id"), nullable=True)
    credito_venta_id = db.Column(
        db.Integer, db.ForeignKey("creditos_venta.id"), nullable=True
    )
    monto = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    # Otros campos
    cobrador_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=False
    )  # Cambiado a no nulo
    caja_id = db.Column(
        db.Integer, db.ForeignKey("cajas.id"), nullable=False
    )  # Cambiado a no nulo
    notas = db.Column(db.Text, nullable=True)

    # Relación bidireccional con back_populates
    venta = db.relationship("Venta", back_populates="abonos", foreign_keys=[venta_id])
    cobrador = db.relationship("Usuario", foreign_keys=[cobrador_id], backref="abonos")
    caja = db.relationship("Caja", foreign_keys=[caja_id])

    @property
    def cliente(self):
        if hasattr(self, "venta") and self.venta and hasattr(self.venta, "cliente"):
            return self.venta.cliente
        return None


class Caja(db.Model):
    __tablename__ = "cajas"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    saldo_inicial = db.Column(db.Integer, nullable=False, default=0)
    saldo_actual = db.Column(db.Integer, nullable=False, default=0)
    fecha_apertura = db.Column(db.DateTime, default=datetime.utcnow)

    # Modificar esta relación para especificar la clave foránea
    movimientos = db.relationship(
        "MovimientoCaja",
        back_populates="caja",
        foreign_keys="MovimientoCaja.caja_id",
        lazy=True,
        cascade="all, delete-orphan",
    )


class MovimientoCaja(db.Model):
    __tablename__ = "movimiento_caja"

    id = db.Column(db.Integer, primary_key=True)
    caja_id = db.Column(db.Integer, db.ForeignKey("cajas.id"), nullable=False)
    tipo = db.Column(
        db.String(20), nullable=False
    )  # 'ingreso' o 'egreso' o 'transferencia'
    monto = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    descripcion = db.Column(db.String(200), nullable=True)

    # Añadir campo venta_id
    venta_id = db.Column(db.Integer, db.ForeignKey("ventas.id"), nullable=True)
    venta = db.relationship(
        "Venta", backref="movimientos_caja", foreign_keys=[venta_id]
    )

    # relación con abono existente
    abono_id = db.Column(db.Integer, db.ForeignKey("abonos.id"), nullable=True)
    abono = db.relationship(
        "Abono", backref="movimientos_caja", foreign_keys=[abono_id]
    )

    # Relación con caja (origen)
    caja = db.relationship("Caja", back_populates="movimientos", foreign_keys=[caja_id])

    # Relación con caja destino (para transferencias)
    caja_destino_id = db.Column(db.Integer, db.ForeignKey("cajas.id"), nullable=True)
    caja_destino = db.relationship(
        "Caja", backref="transferencias_recibidas", foreign_keys=[caja_destino_id]
    )

    def __repr__(self):
        return f"<MovimientoCaja #{self.id} Tipo:{self.tipo} Monto:{self.monto}>"


# CreditoVenta
class CreditoVenta(db.Model):
    __tablename__ = "creditos_venta"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    vendedor_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    total = db.Column(db.Integer, nullable=False)
    saldo_pendiente = db.Column(db.Integer, nullable=False)
    fecha_inicio = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_fin = db.Column(db.DateTime, nullable=True)
    estado = db.Column(db.String(20), default="activo", nullable=False)

    # Relación con Abonos
    abonos = db.relationship(
        "Abono",
        backref="credito_venta",
        lazy=True,
        cascade="all, delete-orphan",
        foreign_keys="Abono.credito_venta_id",
    )

    def __repr__(self):
        return f"<CreditoVenta #{self.id} Cliente:{self.cliente_id} Total:{self.total}>"


class DetalleVenta(db.Model):
    __tablename__ = "detalle_ventas"

    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey("ventas.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Integer, nullable=False)


class Comision(db.Model):
    __tablename__ = "comisiones"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    monto_base = db.Column(db.Integer, nullable=False)
    porcentaje = db.Column(db.Integer, nullable=False)
    monto_comision = db.Column(db.Integer, nullable=False)
    periodo = db.Column(db.String(20), nullable=False)
    pagado = db.Column(db.Boolean, default=False, nullable=False)
    fecha_generacion = db.Column(db.DateTime, default=datetime.utcnow)

    # Nuevos campos para vincular con ventas o abonos
    venta_id = db.Column(db.Integer, db.ForeignKey("ventas.id"), nullable=True)
    abono_id = db.Column(db.Integer, db.ForeignKey("abonos.id"), nullable=True)

    # Relación explícita con Usuario
    usuario = db.relationship(
        "Usuario", foreign_keys=[usuario_id], backref="comisiones"
    )

    # Relaciones con ventas y abonos
    venta = db.relationship("Venta", foreign_keys=[venta_id], backref="comisiones")
    abono = db.relationship("Abono", foreign_keys=[abono_id], backref="comisiones")


class Configuracion(db.Model):
    __tablename__ = "configuraciones"

    id = db.Column(db.Integer, primary_key=True)
    nombre_empresa = db.Column(db.String(100), nullable=False, default="CreditApp")
    direccion = db.Column(db.String(200), nullable=True)
    telefono = db.Column(db.String(20), nullable=True)
    logo = db.Column(db.String(100), nullable=True)
    iva = db.Column(db.Integer, nullable=False, default=0)
    moneda = db.Column(db.String(10), default="$", nullable=False)

    # Comisiones separadas por rol
    porcentaje_comision_vendedor = db.Column(db.Integer, nullable=False, default=5)
    porcentaje_comision_cobrador = db.Column(db.Integer, nullable=False, default=3)
    periodo_comision = db.Column(db.String(20), nullable=False, default="mensual")

    min_password = db.Column(db.Integer, nullable=False, default=6)
    # porcentaje_comision = db.Column(db.Float, nullable=True)


class Producto(db.Model):
    __tablename__ = "productos"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.String(200), nullable=True)
    precio_compra = db.Column(db.Integer, nullable=True)
    precio_venta = db.Column(db.Integer, nullable=False)  # Precio por defecto/kit
    stock = db.Column(db.Integer, nullable=False, default=0)
    stock_minimo = db.Column(db.Integer, nullable=False, default=0)
    unidad = db.Column(db.String(20), nullable=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    # NUEVOS CAMPOS PARA PRECIOS DIFERENCIADOS
    tiene_precio_individual = db.Column(
        db.Boolean, default=False, nullable=False
    )  # Si maneja precio individual
    precio_individual = db.Column(
        db.Integer, nullable=True
    )  # Precio para venta por unidad
    cantidad_kit = db.Column(
        db.Integer, default=1, nullable=False
    )  # Cantidad mínima para precio de kit
    precio_kit = db.Column(
        db.Integer, nullable=True
    )  # Precio unitario para venta en kit

    # Relación con DetalleVenta
    detalles_venta = db.relationship("DetalleVenta", backref="producto", lazy=True)

    def esta_agotado(self):
        return self.stock <= 0

    def stock_bajo(self):
        return self.stock > 0 and self.stock <= self.stock_minimo

    def calcular_precio_unitario(self, cantidad):
        """
        Calcula el precio unitario basado en la cantidad solicitada

        Args:
            cantidad (int): Cantidad de productos a vender

        Returns:
            int: Precio unitario a aplicar
        """
        # Si no tiene configuración de precios diferenciados, usar precio_venta normal
        if not self.tiene_precio_individual:
            return self.precio_venta

        # Si la cantidad es menor al mínimo para kit, usar precio individual
        if cantidad < self.cantidad_kit:
            return self.precio_individual or self.precio_venta

        # Si la cantidad es igual o mayor al kit, usar precio de kit
        return self.precio_kit or self.precio_venta

    def obtener_info_precios(self):
        """
        Retorna información detallada sobre los precios del producto

        Returns:
            dict: Información de precios para mostrar en el frontend
        """
        info = {
            "tiene_precios_diferenciados": self.tiene_precio_individual,
            "precio_base": self.precio_venta,
            "precio_individual": None,
            "precio_kit": None,
            "cantidad_kit": self.cantidad_kit,
            "descripcion_precios": None,
        }

        if self.tiene_precio_individual:
            info["precio_individual"] = self.precio_individual or self.precio_venta
            info["precio_kit"] = self.precio_kit or self.precio_venta

            # Crear descripción legible
            if self.cantidad_kit > 1:
                info["descripcion_precios"] = (
                    f"Individual: ${info['precio_individual']:,} | Kit x{self.cantidad_kit}: ${info['precio_kit']:,} c/u"
                )
            else:
                info["descripcion_precios"] = f"Precio único: ${self.precio_venta:,}"
        else:
            info["descripcion_precios"] = f"Precio único: ${self.precio_venta:,}"

        return info

    def validar_configuracion_precios(self):
        """
        Valida que la configuración de precios sea coherente

        Returns:
            tuple: (bool: es_valida, str: mensaje_error)
        """
        if not self.tiene_precio_individual:
            return True, "Configuración válida"

        # Validar que existan los precios requeridos
        if self.precio_individual is None:
            return False, "El precio individual es requerido"

        if self.precio_kit is None:
            return False, "El precio de kit es requerido"

        # Validar que la cantidad de kit sea mayor a 1
        if self.cantidad_kit <= 1:
            return False, "La cantidad de kit debe ser mayor a 1"

        # Validar que el precio individual sea mayor que el de kit (lógica de negocio)
        if self.precio_individual <= self.precio_kit:
            return False, "El precio individual debe ser mayor que el precio de kit"

        return True, "Configuración válida"


# HISTORIAL DE TRANSFERENCIAS
class TransferenciaVenta(db.Model):
    __tablename__ = "transferencias_venta"

    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey("ventas.id"), nullable=False)
    usuario_origen_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=False
    )
    usuario_destino_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=False
    )
    realizada_por_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=False
    )  # Admin que hizo la transferencia
    motivo = db.Column(db.String(500), nullable=True)  # Motivo de la transferencia
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones
    venta = db.relationship("Venta", backref="transferencias")
    usuario_origen = db.relationship(
        "Usuario", foreign_keys=[usuario_origen_id], backref="transferencias_enviadas"
    )
    usuario_destino = db.relationship(
        "Usuario", foreign_keys=[usuario_destino_id], backref="transferencias_recibidas"
    )
    realizada_por = db.relationship(
        "Usuario", foreign_keys=[realizada_por_id], backref="transferencias_realizadas"
    )

    def __repr__(self):
        return f"<TransferenciaVenta Venta:{self.venta_id} De:{self.usuario_origen_id} A:{self.usuario_destino_id}>"
