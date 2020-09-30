"""
Este modulo carga la Base de datos y agrega los endpoints
"""
import os
from flask import Flask, request, jsonify, url_for
from flask_migrate import Migrate
from flask_swagger import swagger
from flask_cors import CORS
from utils import APIException, generate_sitemap, validate_email_syntax
from admin import setup_admin
from models import db, Usuario, Producto
from smail import sendEmail
from stele import sendTelegram
from flask_jwt_simple import (
    JWTManager, jwt_required, create_jwt, get_jwt_identity
)
app = Flask(__name__)
app.url_map.strict_slashes = False
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DB_CONNECTION_STRING')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY')
MIGRATE = Migrate(app, db)
db.init_app(app)
jwt = JWTManager(app)
CORS(app)
setup_admin(app)
# Maneja/sereliza errores como un objeto JSON 26
@app.errorhandler(APIException)
def handle_invalid_usage(error):
    return jsonify(error.to_dict()), error.status_code
# Genera el sitio con todos los endpoints cargados
@app.route('/')
def sitemap():
    return generate_sitemap(app)
########################35
#
#    Usuarios
#
########################
#Obtiene todos los nombres y filtra por nombre
@app.route("/usuario", methods=["GET", "POST"])
def cr_usuario():
    """
        "GET": devolver lista de todos los usuarios
        "POST": crear un usuario y devolver su información
    """

    # averiguar si es GET o POST
    if request.method == "GET":
        #   seleccionar todos los registros de la tabla usuarios usuarios - usando flask-sqlalchemy
        #   crear una variable lista y asignarle todos los usuarios que devuelva la consulta
        usuarios = Usuario.query.all()
        # verificamos si hay parámetros en la url y filtramos la lista con eso
        nombre = request.args.get("nombre")
        if nombre is not None:
            usuarios_filtrados = filter(lambda usuario: nombre.lower() in usuario.nombre_completo.lower(), usuarios)
        else:
            usuarios_filtrados = usuarios
        #   serializar los objetos de la lista - tendría una lista de diccionarios
        usuarios_serializados = list(map(lambda usuario: usuario.serializar(), usuarios_filtrados))
        print(usuarios_serializados)
        #   devolver la lista jsonificada y 200_OK
        return jsonify(usuarios_serializados), 200
        
    else:
        #   crear una variable y asignarle diccionario con datos para crear donante
        dato_reg = request.json # request.get_json()
        if dato_reg is None:
            return jsonify({
                "resultado": "no envió la informacion para crear el usuario..."
            }), 400
        #   verificar que el diccionario tenga los campos requeridos nombre, apellido, correo, telefono y clave
        if (
            "nombre" not in dato_reg or
            "apellido" not in  dato_reg or
            "nombre_usuario" not in dato_reg or
            #"fecha_nacimiento"not in dato_reg or
            "correo" not in dato_reg or
            "telefono" not in dato_reg or
            "clave" not in dato_reg
        ):
            return jsonify({
                "resultado": "Favor verifique la informacion enviada faltan algunos campos obligatorios"
            }), 400
        #   validar que campos no vengan vacíos y que los campos cumplan con el modelo
        if (
            dato_reg["nombre"] == "" or
            dato_reg["apellido"] == "" or
            dato_reg["nombre_usuario"] == "" or
            dato_reg["correo"] == "" or
            len(str(dato_reg["nombre"])) >= 20 or
            len(str(dato_reg["apellido"])) >= 20 or
            len(str(dato_reg["nombre_usuario"])) >= 20 or
            len(str(dato_reg["correo"])) >= 50 or
            len(str(dato_reg["telefono"])) >= 20 or
            len(str(dato_reg["clave"])) >= 20 or
            len(str(dato_reg["foto_perfil"])) >= 50
        ):
            return jsonify({
                "resultado": "revise los valores de su solicitud"
            }), 400

        # Se procede a validar el correo
        validcorreo = validate_email_syntax(dato_reg["correo"])
        print("Validando correo")
        print(validcorreo)
        if validcorreo == True:

            #   crear una variable y asignarle el nuevo donante con los datos validados
            nuevo_usuario = Usuario.registrarse(
                dato_reg["nombre"].lower().capitalize(),
                dato_reg["apellido"].lower().capitalize(),
                dato_reg["nombre_usuario"],
                dato_reg["fecha_nacimiento"],
                dato_reg["correo"].casefold(),
                dato_reg["telefono"],
                dato_reg["clave"],
                dato_reg["foto_perfil"],
                dato_reg["administrador"],
                dato_reg["suscripcion"]
            )
            
            #   agregar a la sesión de base de datos (sqlalchemy) y hacer commit de la transacción
            db.session.add(nuevo_usuario)
            try:
                db.session.commit()
                #titulocorreo= "Registro satisfactorio"
                #nombre=dato_reg["nombre"]
                #correo=dato_reg["correo"]
                #nombreusuario=dato_reg["nombre_usuario"]
                #mensaje = f"gracias por registrarse su usuario es {nombreusuario}"
                #email = sendEmail(titulocorreo, nombre, correo, mensaje)
                # devolvemos el nuevo donante serializado y 201_CREATED
                return jsonify(nuevo_usuario.serializar()), 201
            except Exception as error:
                db.session.rollback()
                print(f"{error.args} {type(error)}")
                # devolvemos "mira, tuvimos este error..."
                return jsonify({
                    "resultado": f"{error.args}"
                }), 500
        else:
            #Correo invalido
            status_code = 400
            response_body = {
                "result": "HTTP_400_BAD_REQUEST. Verifique el correo ingresado."
            }
            return  jsonify(response_body), status_code

#Obtiene usuarios segun su id para acualizar o eliminar solo por admin
@app.route("/usuario/<id>", methods=["GET", "PUT", "DELETE"])
@jwt_required

def crud_usuario(id):
    """
        GET: devolver el detalle de un usuario específico
        PUT actualizar datos del usuario específico,
            guardar en base de datos y devolver el detalle
        DELETE: eliminar el usuario específico y devolver 204 
    """
    usuario_id_jwt = get_jwt_identity()
    usuario= Usuario.query.get(usuario_id_jwt)
    admin = usuario.administrador
    print(usuario_id_jwt)
    print(usuario)
    print(admin)
    # crear una variable y asignar el donante específico
    usuario = Usuario.query.get(id)
    # verificar si el donante con id donante_id existe
    if isinstance(usuario, Usuario):
        if request.method == "GET":
            # devolver el donante serializado y jsonificado. Y 200
            return jsonify(usuario.serializar()), 200
        elif request.method == "PUT":
            # recuperar diccionario con insumos del body del request
            diccionario = request.get_json()
            # actualizar propiedades que vengan en el diccionario
            print(diccionario)
            usuario.actualizar_usuario(diccionario)
            # guardar en base de datos, hacer commit
            try:
                db.session.commit()
                # devolver el donante serializado y jsonificado. Y 200 
                return jsonify(usuario.serializar()), 200
            except Exception as error:
                db.session.rollback()
                print(f"{error.args} {type(error)}")
                return jsonify({
                    "resultado": f"{error.args}"
                }), 500
        else:
            # remover el donante específico de la sesión de base de datos
            db.session.delete(usuario)
            # hacer commit y devolver 204
            try:
                db.session.commit()
                return jsonify({
                    "resultado": "el contacto fue eliminado"
                }), 204
            except Exception as error:
                db.session.rollback()
                print(f"{error.args} {type(error)}")
                return jsonify({
                    "resultado": f"{error.args}"
                }), 500
    else:
        # el usuario no existe!
        return jsonify({
            "resultado": "el contacto que ingreso no existe..."
        }), 404



########################201
#
#    Productos
#
######################## 211


###################        CRUD de Vendegram !!!    ######################  214
#####  1.-Obtenga una lista de todos los productos GET /producto;                         tambien filtra por nombre si recibe el parametro en la url   #########
    ##########  2.- Crear un nuevo producto POST /producto ########### 

###################        CRUD de Vendegram !!!    ######################  
#####  1.-Obtenga una lista de todos los productos GET /producto;                         tambien filtra por nombre si recibe el parametro en la url   #########
    ##########  2.- Crear un nuevo producto POST /producto ########### 

@app.route('/producto', methods=["GET", "POST"])

def todos_productos():
    if request.method == "GET":
        producto = Producto.query.all()
        # verificamos si hay parámetros en la url y filtramos la lista con eso si titulo no esta vacio producto_filtrado busca en producto.titulo si el requerimiento es igual a algun titulo ya creado para filtrarlo.
        titulo = request.args.get("titulo")
        if titulo is not None:
            producto_filtrado = filter(lambda producto: titulo.lower() in producto.titulo, producto) 
        else:
            producto_filtrado = producto
        #   serializar los objetos de la lista - tendría una lista de diccionarios
        producto_lista = list(map(lambda producto: producto.serialize(), producto_filtrado))     
        return jsonify(producto_lista), 200
    ###Validaciones de caracteres y que los campos no esten vacios###
    else:
        insumos_producto = request.json
        if insumos_producto is None:
            return jsonify({
                "resultado": "no envio insumos para crear el producto" 
            }), 400
         # verificar que el diccionario tenga titulo, descripcion, foto,etc
        if (
            "titulo" not in insumos_producto or
            "descripcion" not in insumos_producto or
            "foto" not in insumos_producto or
            "cantidad" not in insumos_producto or
            "precio" not in insumos_producto or
           "etiqueta_uno" not in insumos_producto
        ):
            return jsonify({
                "resultado": "revise las propiedades de su solicitud"
            }), 400
        #validar que campos no vengan vacíos y que los string tenga sus respectivos caracteres
        if (
            insumos_producto["titulo"] == "" or
            insumos_producto["descripcion"] == "" or
            insumos_producto["foto"] == "" or
            insumos_producto["etiqueta_uno"] == "" or         
            len(str(insumos_producto["titulo"])) > 100 or
            len(str(insumos_producto["descripcion"])) > 2000 or
            len(str(insumos_producto["foto"])) > 200 or
            int(insumos_producto["cantidad"]) < 0 or
            float(insumos_producto["precio"]) < 0

        ):
            return jsonify({
                "resultado": "revise los valores de su solicitud"
            }), 400

        # METODO POST: crear una variable y asignarle el nuevo producto con los datos validados
        body = request.get_json()        
        producto = Producto(titulo=body['titulo'], foto=body['foto'], descripcion=body['descripcion'],
        precio=body['precio'], cantidad=body['cantidad'], etiqueta_uno=body['etiqueta_uno'], 
        etiqueta_dos=body['etiqueta_dos'],etiqueta_tres=body['etiqueta_tres'])
        #   agregar a la sesión de base de datos (sqlalchemy) y hacer commit de la transacción
        print("imprimiento")
        print (jsonify(producto.serialize()))
        db.session.add(producto)
        try:
            db.session.commit()
            # devolvemos el nuevo donante serializado y 201_CREATED
            return jsonify(producto.serialize()), 201
        except Exception as error:
            db.session.rollback()
            print(f"{error.args} {type(error)}")
            # devolvemos "mira, tuvimos este error..."
            return jsonify({
                "resultado1": f"{error.args}"
            }), 500

##########  4.- Eliminar un producto DELETE /producto/{producto_id} ########### 

@app.route('/producto/<int:producto_id>', methods=['DELETE'])
def eliminar_producto(producto_id):
    producto = Producto.query.get(producto_id)
    if producto is None:
        raise APIException('producto no encontrado', status_code=404)
    else:
        # remover el producto específico de la sesión de base de datos
        db.session.delete(producto)
        # hacer commit y devolver 200
        try:
            db.session.commit()
            response_body = {
           "msg": "El producto a sido eliminado"
           }
            return jsonify(response_body), 200
        except Exception as error:
            db.session.rollback()
            print(f"{error.args} {type(error)}")
            return jsonify({
                "resultado al eliminar un producto": f"{error.args}"
            }), 500


##########  5.- Actualiza el producto UPDATE /producto/{producto_id} ###########     
@app.route('/producto/<int:producto_id>', methods=['PUT'])
def actualizar_producto(producto_id):
    body = request.get_json()
    producto = Producto.query.get(producto_id)
    if producto is None:
        raise APIException('producto no encontrado', status_code=404) 
    producto.update(body)
    try:
        db.session.commit()
        # devolvemos el nuevo producto serializado y 200_CREATED
        return jsonify(producto.serialize()), 200
    except Exception as error:
        db.session.rollback()
        print(f"{error.args} {type(error)}")
        # devolvemos "mira, tuvimos este error..."
        return jsonify({
            "Presente error al actualizar un producto": f"{error.args}"
        }), 500    



















########################356
#
#    Envoar ccorreo o mensajes telegram
#
########################

#Para enviar correo usando la cuenta de VendeGram
@app.route("/SendCorreo", methods = ['POST'])
def SendCorreo():

    # Verificamos el método
    if (request.method == 'POST'):

        # Obtenemos los datos de la forma
        titulocorreo = request.form['titulocorreo']
        nombre = request.form['nombre']
        correo = request.form['correo']
        mensaje = request.form['mensaje']
        respuesta = sendEmail(titulocorreo, nombre, correo, mensaje)
        #flash(respuesta, 'alert-success')
        #print(respuesta)
        # Redirigimos a mensaje
        return jsonify(respuesta), 200

# Para enviar mensajes por Telegram mendiante su API
@app.route("/SendTelegram", methods = ['POST'])
def SendTelegram():

    # Verificamos el método
    if (request.method == 'POST'):

        # Obtenemos los datos de la forma
        
        nombre = request.form['nombre']
        telegram = request.form['telegram']
        mensaje = request.form['mensaje']

        #idTelegram = " {} "+telegram
        response = sendTelegram(nombre, telegram, mensaje)
        
        return response


########################416
#
#    Login
#
########################

@app.route("/ingresar", methods = ['POST'])
def manejar_ingreso():
    '''
    POST: Se verifica si el usuario existe y luego se verifica la clave. Se recibe el correo y clave
    '''

    input_data = request.json
    if ("correo" not in input_data or
        "clave" not in input_data 
    ):
        return jsonify({
            "resultado":"favor ingresar la el usuario o clave para verificar la informacion"
            }),400

    else:
        usuario = Usuario.query.filter_by(
            correo=input_data["correo"]
        ).one_or_none()
        if usuario is None:
            return jsonify({
            "resultado":"La informacion ingresada es incorrecta valide sus datos"
            }), 400
        else:
            if usuario.check_password(input_data["clave"]):
                #exito
                token = create_jwt(identity = usuario.id)
                return jsonify({
                    "token": token,
                    "id_usuario": usuario.id,
                    "correo":usuario.correo,
                    "isadmin":usuario.administrador
                }), 200

            else:
                return jsonify({
            "resultado":"Verifique su clave"
            }), 400





# this only runs if `$ python src/main.py` is executed
if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=PORT, debug=False)
