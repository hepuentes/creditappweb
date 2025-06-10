from decimal import Decimal, InvalidOperation
from wtforms import ValidationError
from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField,
    SelectField, FloatField, IntegerField, HiddenField, TextAreaField,
    FileField
)
from wtforms.validators import (
    DataRequired, Email, Length, EqualTo,
    NumberRange, Optional, InputRequired  
)

# --- Formulario de Login ---
class LoginForm(FlaskForm):
    email = StringField(
        'Email',
        validators=[DataRequired(), Email(message='Email inválido')]
    )
    password = PasswordField(
        'Contraseña',
        validators=[DataRequired()]
    )
    remember = BooleanField('Recuérdame')
    submit = SubmitField('Iniciar Sesión')


# --- Formulario de Usuarios ---
class UsuarioForm(FlaskForm):
    nombre = StringField(
        'Nombre',
        validators=[DataRequired(), Length(min=2, max=100)]
    )
    email = StringField(
        'Email',
        validators=[DataRequired(), Email(message='Email inválido')]
    )
    password = PasswordField(
        'Contraseña',
        validators=[Optional(), Length(min=6)]
    )
    confirm_password = PasswordField(
        'Confirmar Contraseña',
        validators=[EqualTo('password', message='Las contraseñas deben coincidir')]
    )
    rol = SelectField(
        'Rol',
        choices=[('administrador','Administrador'),('vendedor','Vendedor'),('cobrador','Cobrador')],
        validators=[DataRequired()]
    )
    activo = BooleanField('Activo', default=True)
    submit = SubmitField('Guardar Usuario')


# --- Formulario de Clientes ---
class ClienteForm(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired()])
    cedula = StringField('Cédula/NIT', validators=[DataRequired()])
    telefono = StringField('Teléfono', validators=[Optional(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Email(message='Email inválido')])
    direccion = StringField('Dirección', validators=[Optional(), Length(max=200)])
    submit = SubmitField('Guardar Cliente')


# --- Formulario de Productos ---
class ProductoForm(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired()])
    codigo = StringField('Código', validators=[DataRequired()])
    descripcion = StringField('Descripción', validators=[Optional(), Length(max=200)])
    precio_compra = FloatField('Precio de Compra', validators=[Optional(), NumberRange(min=0)])
    precio_venta = FloatField('Precio de Venta', validators=[DataRequired(), NumberRange(min=0)])
    stock = IntegerField('Stock', validators=[DataRequired(), NumberRange(min=0)])
    stock_minimo = IntegerField('Stock Mínimo', validators=[DataRequired(), NumberRange(min=0)])
    unidad = StringField('Unidad', validators=[Optional()])
    submit = SubmitField('Guardar Producto')


# --- Formulario de Ventas ---
class VentaForm(FlaskForm):
    cliente = SelectField('Cliente', coerce=int, validators=[DataRequired()])
    caja = SelectField('Caja', coerce=int, validators=[DataRequired()])
    tipo = SelectField(
        'Tipo de Venta',
        choices=[('contado','Contado'),('credito','Crédito')],
        validators=[DataRequired()]
    )
    # Los productos seleccionados se envían en un campo oculto en JSON
    productos = HiddenField('Productos')  
    submit = SubmitField('Registrar Venta')


# --- Formulario de Abonos ---
class AbonoForm(FlaskForm):
    cliente_id = SelectField('Cliente', coerce=int, validators=[Optional()])  # Cambiado a Optional
    tipo_credito = SelectField('Tipo de Crédito', 
                              choices=[('venta', 'Venta a Crédito'), ('credito', 'Crédito Directo')], 
                              default='venta',
                              validators=[Optional()])
    venta_id = SelectField('Venta/Crédito', coerce=int, validators=[Optional()])  # Cambiado a Optional
    credito_id = HiddenField('ID Crédito')
    credito_venta_id = HiddenField('ID Crédito Venta')
    monto = StringField('Monto', validators=[Optional()])  # Validación manual en controlador
    caja_id = SelectField('Caja', coerce=int, validators=[Optional()])  # Validación manual en controlador
    notas = TextAreaField('Notas', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Registrar Abono')
    
    def validate_venta_id(self, field):
        # Permitir -1 temporalmente durante la selección, pero no en submit final
        if field.data == -1:
            # Solo permitir -1 si estamos en modo de carga, no en submit
            import flask
            if flask.request.method == 'POST':
                from wtforms import ValidationError
                raise ValidationError('Debe seleccionar una venta válida')
        return True
            
# --- Formulario de Créditos ---
class CreditoForm(FlaskForm):
    cliente = SelectField('Cliente', coerce=int, validators=[DataRequired()])
    monto = FloatField('Monto', validators=[DataRequired(), NumberRange(min=0.01)])
    plazo = IntegerField('Plazo (días)', validators=[DataRequired(), NumberRange(min=1)])
    tasa = FloatField('Tasa (%)', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Registrar Crédito')


# --- Formulario de Cajas ---
class CajaForm(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired(), Length(max=100)])
    tipo = SelectField('Tipo', choices=[
        ('efectivo', 'Efectivo'),
        ('nequi', 'Nequi'),
        ('daviplata', 'Daviplata'),
        ('transferencia', 'Transferencia Bancaria')
    ], validators=[DataRequired()])
    # Cambiar de DataRequired a InputRequired para permitir valores de 0
    saldo_inicial = FloatField('Saldo Inicial', 
        validators=[
            InputRequired(message="Este campo es obligatorio"),  # Cambiado de DataRequired a InputRequired
            NumberRange(min=0, message="El saldo inicial debe ser mayor o igual a 0")
        ])
    submit = SubmitField('Crear Caja')
    
# --- Formulario de Movimientos de Caja ---
class MovimientoCajaForm(FlaskForm):
    tipo = SelectField(
        'Tipo',
        choices=[('entrada','Entrada'),('salida','Salida'),('transferencia','Transferencia')],
        validators=[DataRequired()]
    )
    monto = FloatField('Monto', validators=[DataRequired(), NumberRange(min=0.01)])
    concepto = StringField('Concepto', validators=[DataRequired(), Length(max=100)])
    caja_destino_id = SelectField(
        'Caja Destino',
        coerce=lambda x: int(x) if x else None,
        validators=[Optional()]
    )
    submit = SubmitField('Registrar Movimiento')


# --- Formulario de Configuración ---
class ConfiguracionForm(FlaskForm):
    nombre_empresa = StringField('Nombre de la Empresa', validators=[DataRequired(), Length(max=100)])
    direccion = StringField('Dirección', validators=[Optional(), Length(max=200)])
    telefono = StringField('Teléfono', validators=[Optional(), Length(max=20)])
    logo = FileField('Logo de la Empresa')
    moneda = StringField('Símbolo de Moneda', validators=[DataRequired(), Length(max=5)])
    iva = FloatField(
        'IVA (%)', 
        validators=[DataRequired(), NumberRange(min=0, max=100)]
    )
    
    # Comisiones separadas por rol
    porcentaje_comision_vendedor = FloatField(
        'Comisión Vendedores (%)',
        validators=[DataRequired(), NumberRange(min=0, max=100)]
    )
    porcentaje_comision_cobrador = FloatField(
        'Comisión Cobradores (%)',
        validators=[DataRequired(), NumberRange(min=0, max=100)]
    )
    periodo_comision = SelectField(
        'Periodo de Comisión',
        choices=[('quincenal','Quincenal'),('mensual','Mensual')]
    )
    min_password = IntegerField('Tamaño Mínimo de Contraseña', validators=[DataRequired(), NumberRange(min=4, max=20)])
    submit = SubmitField('Guardar Configuración')


# --- Formulario de Reportes de Comisiones ---
class ReporteComisionesForm(FlaskForm):
    usuario_id = SelectField('Usuario', coerce=int, validators=[DataRequired()])
    fecha_inicio = StringField('Fecha Inicio', validators=[DataRequired()])
    fecha_fin = StringField('Fecha Fin', validators=[DataRequired()])
    submit = SubmitField('Generar Reporte')

# Formulario específico para editar abonos
class AbonoEditForm(FlaskForm):
    monto = StringField(
        'Monto',
        validators=[DataRequired(message="El monto es obligatorio")]
    )
    caja_id = SelectField(
        'Caja',
        coerce=int,
        validators=[DataRequired(message="Debe seleccionar una caja")]
    )
    notas = TextAreaField(
        'Notas',
        validators=[Optional(), Length(max=500)]
    )
    submit = SubmitField('Guardar Cambios')

    def __init__(self, abono=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.abono = abono
    
    def validate_monto(self, field):
        try:
            monto_int = int(field.data.strip().replace(',', '').replace('.', ''))
            
            if monto_int <= 0:
                raise ValidationError("El monto debe ser mayor a cero")
            
            if self.abono and self.abono.venta:
                saldo_disponible = self.abono.venta.saldo_pendiente + self.abono.monto
                if monto_int > saldo_disponible:
                    raise ValidationError(f"El monto no puede ser mayor al saldo disponible (${saldo_disponible:,.0f})")
                    
        except ValueError:
            raise ValidationError("Formato del monto no válido")
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError("Error al validar el monto")