from flask import Blueprint, request, jsonify
from modules.auth.decoraters import auth_required, member_required, error_handler
from modules.utils.db import DBConnect
from modules.storefront.models import Product, Order, OrderItem
from utils.clerk_auth import require_clerk_auth
from sqlalchemy import func

storefront_blueprint = Blueprint("storefront", __name__)
db_connect = DBConnect()

# Helper function to get organization by prefix
def get_organization_by_prefix(db, org_prefix):
    from modules.organizations.models import Organization
    org = db.query(Organization).filter(Organization.prefix == org_prefix).first()
    if not org:
        return None
    return org

# PRODUCT ENDPOINTS
@storefront_blueprint.route("/<string:org_prefix>/products", methods=["GET"])
@error_handler
def get_products(org_prefix):
    """Get all products for an organization"""
    db = next(db_connect.get_db())
    try:
        org = get_organization_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        products = db_connect.get_storefront_products(db, org.id)
        return jsonify([{
            'id': p.id,
            'name': p.name,
            'description': p.description,
            'price': p.price,
            'stock': p.stock,
            'image_url': p.image_url,
            'organization_id': p.organization_id,
            'created_at': p.created_at.isoformat() if p.created_at else None,
            'updated_at': p.updated_at.isoformat() if p.updated_at else None
        } for p in products]), 200
    finally:
        db.close()

@storefront_blueprint.route("/<string:org_prefix>/products/<int:product_id>", methods=["GET"])
@error_handler
def get_product(org_prefix, product_id):
    """Get a specific product by ID for an organization"""
    db = next(db_connect.get_db())
    try:
        org = get_organization_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        product = db_connect.get_storefront_product(db, product_id, org.id)
        if not product:
            return jsonify({"error": "Product not found"}), 404
            
        return jsonify({
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'price': product.price,
            'stock': product.stock,
            'image_url': product.image_url,
            'organization_id': product.organization_id,
            'created_at': product.created_at.isoformat() if product.created_at else None,
            'updated_at': product.updated_at.isoformat() if product.updated_at else None
        }), 200
    finally:
        db.close()

@storefront_blueprint.route("/<string:org_prefix>/products", methods=["POST"])
@auth_required
@error_handler
def create_product(org_prefix):
    """Create a new product for an organization"""
    data = request.get_json()
    
    # Validate required fields
    if not data.get('name'):
        return jsonify({"error": "Product name is required"}), 400
    if not data.get('price'):
        return jsonify({"error": "Product price is required"}), 400
    if not data.get('stock'):
        return jsonify({"error": "Product stock is required"}), 400
    
    new_product = Product(
        name=data['name'],
        description=data.get('description', ''),
        price=float(data['price']),
        stock=int(data['stock']),
        image_url=data.get('image_url', '')
    )
    
    db = next(db_connect.get_db())
    try:
        org = get_organization_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        created_product = db_connect.create_storefront_product(db, new_product, org.id)
        return jsonify({
            'message': 'Product created successfully', 
            'id': created_product.id,
            'product': {
                'id': created_product.id,
                'name': created_product.name,
                'description': created_product.description,
                'price': created_product.price,
                'stock': created_product.stock,
                'image_url': created_product.image_url,
                'organization_id': created_product.organization_id
            }
        }), 201
    finally:
        db.close()

@storefront_blueprint.route("/<string:org_prefix>/products/<int:product_id>", methods=["PUT"])
@auth_required
@error_handler
def update_product(org_prefix, product_id):
    """Update a product for an organization"""
    db = next(db_connect.get_db())
    try:
        org = get_organization_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        product = db_connect.get_storefront_product(db, product_id, org.id)
        if not product:
            return jsonify({"error": "Product not found"}), 404
            
        data = request.get_json()
        
        # Update fields if provided
        if 'name' in data:
            product.name = data['name']
        if 'description' in data:
            product.description = data['description']
        if 'price' in data:
            product.price = float(data['price'])
        if 'stock' in data:
            product.stock = int(data['stock'])
        if 'image_url' in data:
            product.image_url = data['image_url']
        
        db.commit()
        return jsonify({
            'message': 'Product updated successfully',
            'product': {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'price': product.price,
                'stock': product.stock,
                'image_url': product.image_url,
                'organization_id': product.organization_id
            }
        }), 200
    finally:
        db.close()

@storefront_blueprint.route("/<string:org_prefix>/products/<int:product_id>", methods=["DELETE"])
@auth_required
@error_handler
def delete_product(org_prefix, product_id):
    """Delete a product for an organization"""
    db = next(db_connect.get_db())
    try:
        org = get_organization_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        success = db_connect.delete_storefront_product(db, product_id, org.id)
        if not success:
            return jsonify({"error": "Product not found"}), 404
            
        return jsonify({'message': 'Product deleted successfully'}), 200
    finally:
        db.close()

# ORDER ENDPOINTS
@storefront_blueprint.route("/<string:org_prefix>/orders", methods=["GET"])
@auth_required
@error_handler
def get_orders(org_prefix):
    """Get all orders for an organization"""
    db = next(db_connect.get_db())
    try:
        org = get_organization_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        orders = db_connect.get_storefront_orders(db, org.id)
        return jsonify([{
            'id': o.id,
            'user_id': o.user_id,
            'total_amount': o.total_amount,
            'status': o.status,
            'message': o.message,
            'created_at': o.created_at.isoformat(),
            'updated_at': o.updated_at.isoformat() if o.updated_at else None,
            'organization_id': o.organization_id,
            'user_name': o.user.name if o.user else 'Unknown User',
            'items': [{
                'id': item.id,
                'product_id': item.product_id,
                'quantity': item.quantity,
                'price_at_time': item.price_at_time
            } for item in o.items]
        } for o in orders]), 200
    finally:
        db.close()

@storefront_blueprint.route("/<string:org_prefix>/orders/<int:order_id>", methods=["GET"])
@auth_required
@error_handler
def get_order(org_prefix, order_id):
    """Get a specific order by ID for an organization"""
    db = next(db_connect.get_db())
    try:
        org = get_organization_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        order = db_connect.get_storefront_order(db, order_id, org.id)
        if not order:
            return jsonify({"error": "Order not found"}), 404
            
        return jsonify({
            'id': order.id,
            'user_id': order.user_id,
            'total_amount': order.total_amount,
            'status': order.status,
            'created_at': order.created_at.isoformat(),
            'updated_at': order.updated_at.isoformat() if order.updated_at else None,
            'organization_id': order.organization_id,
            'items': [{
                'id': item.id,
                'product_id': item.product_id,
                'quantity': item.quantity,
                'price_at_time': item.price_at_time
            } for item in order.items]
        }), 200
    finally:
        db.close()

@storefront_blueprint.route("/<string:org_prefix>/orders", methods=["POST"])
@error_handler
def create_order(org_prefix):
    """Create a new order for an organization (public endpoint for customer purchases)"""
    data = request.get_json()
    
    # Validate required fields
    if not data.get('user_id'):
        return jsonify({"error": "User ID is required"}), 400
    if not data.get('total_amount'):
        return jsonify({"error": "Total amount is required"}), 400
    if not data.get('items') or len(data['items']) == 0:
        return jsonify({"error": "Order items are required"}), 400
    
    new_order = Order(
        user_id=data['user_id'],
        total_amount=float(data['total_amount']),
        status=data.get('status', 'pending')
    )
    
    # Prepare order items
    order_items = []
    for item in data['items']:
        if not all(k in item for k in ['product_id', 'quantity', 'price']):
            return jsonify({"error": "Each item must have product_id, quantity, and price"}), 400
        order_items.append(OrderItem(
            product_id=int(item['product_id']),
            quantity=int(item['quantity']),
            price_at_time=float(item['price'])
        ))
    
    db = next(db_connect.get_db())
    try:
        org = get_organization_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        # Validate that all products exist and have sufficient stock
        for item in order_items:
            product = db_connect.get_storefront_product(db, item.product_id, org.id)
            if not product:
                return jsonify({"error": f"Product {item.product_id} not found"}), 404
            if product.stock < item.quantity:
                return jsonify({"error": f"Insufficient stock for product {product.name}"}), 400
            
            # Update stock
            product.stock -= item.quantity
            
        created_order = db_connect.create_storefront_order(db, new_order, order_items, org.id)
        return jsonify({
            'message': 'Order created successfully', 
            'id': created_order.id,
            'order': {
                'id': created_order.id,
                'user_id': created_order.user_id,
                'total_amount': created_order.total_amount,
                'status': created_order.status,
                'created_at': created_order.created_at.isoformat()
            }
        }), 201
    finally:
        db.close()

@storefront_blueprint.route("/<string:org_prefix>/orders/<int:order_id>", methods=["PUT"])
@auth_required
@error_handler
def update_order_status(org_prefix, order_id):
    """Update order status for an organization"""
    db = next(db_connect.get_db())
    try:
        org = get_organization_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        order = db_connect.get_storefront_order(db, order_id, org.id)
        if not order:
            return jsonify({"error": "Order not found"}), 404
            
        data = request.get_json()
        
        # Update status if provided
        if 'status' in data:
            valid_statuses = ['pending', 'processing', 'shipped', 'delivered', 'cancelled']
            if data['status'] not in valid_statuses:
                return jsonify({"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}), 400
            order.status = data['status']
        
        # Update message if provided
        if 'message' in data:
            order.message = data['message']
        
        db.commit()
        return jsonify({
            'message': 'Order updated successfully',
            'order': {
                'id': order.id,
                'user_id': order.user_id,
                'total_amount': order.total_amount,
                'status': order.status,
                'message': order.message,
                'updated_at': order.updated_at.isoformat() if order.updated_at else None
            }
        }), 200
    finally:
        db.close()

@storefront_blueprint.route("/<string:org_prefix>/orders/<int:order_id>", methods=["DELETE"])
@auth_required
@error_handler
def delete_order(org_prefix, order_id):
    """Delete an order for an organization"""
    db = next(db_connect.get_db())
    try:
        org = get_organization_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        order = db_connect.get_storefront_order(db, order_id, org.id)
        if not order:
            return jsonify({"error": "Order not found"}), 404
            
        # Restore stock for cancelled orders
        if order.status not in ['cancelled', 'delivered']:
            for item in order.items:
                product = db_connect.get_storefront_product(db, item.product_id, org.id)
                if product:
                    product.stock += item.quantity
            
        db.delete(order)
        db.commit()
        return jsonify({'message': 'Order deleted successfully'}), 200
    finally:
        db.close()

# STORE FRONT ENDPOINTS (Public access for customers)
@storefront_blueprint.route("/<string:org_prefix>/store", methods=["GET"])
@error_handler
def get_store_products(org_prefix):
    """Get all available products for public store front"""
    db = next(db_connect.get_db())
    try:
        org = get_organization_by_prefix(db, org_prefix)
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        products = db_connect.get_storefront_products(db, org.id)
        # Only return products with stock > 0 for the store front
        available_products = [p for p in products if p.stock > 0]
        
        return jsonify({
            'organization': {
                'name': org.name,
                'prefix': org.prefix,
                'description': org.description
            },
            'products': [{
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'price': p.price,
                'stock': p.stock,
                'image_url': p.image_url
            } for p in available_products]
        }), 200
    finally:
        db.close()

@storefront_blueprint.route("/<string:org_prefix>/store/purchase", methods=["POST"])
@error_handler
def purchase_products(org_prefix):
    """Public endpoint for customers to purchase products"""
    return create_order(org_prefix)  # Reuse the create_order function

# MEMBER-SPECIFIC ENDPOINTS (Requires organization membership)
@storefront_blueprint.route("/<string:org_prefix>/members/store", methods=["GET"])
@member_required
@error_handler
def get_member_store(org_prefix, **kwargs):
    """Get store front for organization members (may include member-only products)"""
    user_discord_id = kwargs.get('user_discord_id')
    organization = kwargs.get('organization')
    
    # Get or create user in this organization
    from modules.points.api import get_or_create_user
    user = get_or_create_user(user_discord_id, organization.id)
    
    db = next(db_connect.get_db())
    try:
        products = db_connect.get_storefront_products(db, organization.id)
        # Only return products with stock > 0 for the store front
        available_products = [p for p in products if p.stock > 0]
        
        return jsonify({
            'organization': {
                'name': organization.name,
                'prefix': organization.prefix,
                'description': organization.description
            },
            'user_info': {
                'discord_id': user_discord_id,
                'user_id': user.id if user else None,
                'is_member': True
            },
            'products': [{
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'price': p.price,
                'stock': p.stock,
                'image_url': p.image_url,
                'created_at': p.created_at.isoformat() if p.created_at else None,
                'updated_at': p.updated_at.isoformat() if p.updated_at else None
            } for p in available_products]
        }), 200
    finally:
        db.close()

@storefront_blueprint.route("/<string:org_prefix>/members/orders", methods=["GET"])
@member_required
@error_handler
def get_member_orders(org_prefix, **kwargs):
    """Get orders for the authenticated member"""
    user_discord_id = kwargs.get('user_discord_id')
    organization = kwargs.get('organization')
    
    # Get or create user in this organization
    from modules.points.api import get_or_create_user
    user = get_or_create_user(user_discord_id, organization.id)
    
    if not user:
        return jsonify({"error": "Could not create or find user"}), 500
    
    db = next(db_connect.get_db())
    try:
        # Get orders for this specific user in this organization
        from modules.storefront.models import Order
        orders = db.query(Order).filter(
            Order.organization_id == organization.id,
            Order.user_id == user.id
        ).order_by(Order.created_at.desc()).all()
        
        return jsonify([{
            'id': o.id,
            'total_amount': o.total_amount,
            'status': o.status,
            'message': o.message,
            'created_at': o.created_at.isoformat(),
            'updated_at': o.updated_at.isoformat() if o.updated_at else None,
            'items': [{
                'id': item.id,
                'product_id': item.product_id,
                'quantity': item.quantity,
                'price_at_time': item.price_at_time,
                'product_name': item.product.name if item.product else 'Unknown Product'
            } for item in o.items]
        } for o in orders]), 200
    finally:
        db.close()

@storefront_blueprint.route("/<string:org_prefix>/members/orders", methods=["POST"])
@member_required
@error_handler
def create_member_order(org_prefix, **kwargs):
    """Create a new order for authenticated member"""
    user_discord_id = kwargs.get('user_discord_id')
    organization = kwargs.get('organization')
    
    # Get or create user in this organization
    from modules.points.api import get_or_create_user
    user = get_or_create_user(user_discord_id, organization.id)
    
    if not user:
        return jsonify({"error": "Could not create or find user"}), 500
    
    data = request.get_json()
    
    # Validate required fields
    if not data.get('total_amount'):
        return jsonify({"error": "Total amount is required"}), 400
    if not data.get('items') or len(data['items']) == 0:
        return jsonify({"error": "Order items are required"}), 400
    
    new_order = Order(
        user_id=user.id,  # Use proper user ID
        discord_user_id=user_discord_id,  # Keep for backward compatibility
        total_amount=float(data['total_amount']),
        status='pending'
    )
    
    # Prepare order items
    order_items = []
    for item in data['items']:
        if not all(k in item for k in ['product_id', 'quantity', 'price']):
            return jsonify({"error": "Each item must have product_id, quantity, and price"}), 400
        order_items.append(OrderItem(
            product_id=int(item['product_id']),
            quantity=int(item['quantity']),
            price_at_time=float(item['price'])
        ))
    
    db = next(db_connect.get_db())
    try:
        # Validate that all products exist and have sufficient stock
        for item in order_items:
            product = db_connect.get_storefront_product(db, item.product_id, organization.id)
            if not product:
                return jsonify({"error": f"Product {item.product_id} not found"}), 404
            if product.stock < item.quantity:
                return jsonify({"error": f"Insufficient stock for product {product.name}"}), 400
            
            # Update stock
            product.stock -= item.quantity
            
        created_order = db_connect.create_storefront_order(db, new_order, order_items, organization.id)
        return jsonify({
            'message': 'Order created successfully', 
            'id': created_order.id,
            'order': {
                'id': created_order.id,
                'user_id': created_order.user_id,
                'total_amount': created_order.total_amount,
                'status': created_order.status,
                'created_at': created_order.created_at.isoformat()
            }
        }), 201
    finally:
        db.close()

@storefront_blueprint.route("/<string:org_prefix>/members/orders/<int:order_id>", methods=["GET"])
@member_required
@error_handler
def get_member_order(org_prefix, order_id, **kwargs):
    """Get a specific order for the authenticated member"""
    user_discord_id = kwargs.get('user_discord_id')
    organization = kwargs.get('organization')
    
    db = next(db_connect.get_db())
    try:
        # Get order for this specific user in this organization
        from modules.storefront.models import Order
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.organization_id == organization.id,
            Order.user_id == user_discord_id
        ).first()
        
        if not order:
            return jsonify({"error": "Order not found"}), 404
        
        return jsonify({
            'id': order.id,
            'total_amount': order.total_amount,
            'status': order.status,
            'created_at': order.created_at.isoformat(),
            'updated_at': order.updated_at.isoformat() if order.updated_at else None,
            'items': [{
                'id': item.id,
                'product_id': item.product_id,
                'quantity': item.quantity,
                'price_at_time': item.price_at_time,
                'product_name': item.product.name if item.product else 'Unknown Product'
            } for item in order.items]
        }), 200
    finally:
        db.close() 

# MEMBER POINTS ENDPOINT (for storefront)
@storefront_blueprint.route("/<string:org_prefix>/members/points", methods=["GET"])
@member_required
@error_handler
def get_user_points_public(org_prefix, **kwargs):
    """Get authenticated member's points balance (storefront endpoint)"""
    db = next(db_connect.get_db())
    try:
        from modules.points.models import User, Points, UserOrganizationMembership

        user_discord_id = kwargs.get('user_discord_id')
        organization = kwargs.get('organization')

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        if not user_discord_id:
            return jsonify({"error": "User not found"}), 404

        # Find user based on authenticated context
        user = db.query(User).filter_by(discord_id=user_discord_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Check membership
        membership = db.query(UserOrganizationMembership).filter_by(
            user_id=user.id,
            organization_id=organization.id,
            is_active=True
        ).first()

        if not membership:
            return jsonify({"error": "User is not a member of this organization"}), 403

        # Calculate total points using database aggregation
        total_points = db.query(func.sum(Points.points)).filter_by(
            user_id=user.id,
            organization_id=organization.id
        ).scalar() or 0

        # Get last 20 points records for breakdown
        points_records = db.query(Points).filter_by(
            user_id=user.id,
            organization_id=organization.id
        ).order_by(Points.timestamp.desc()).limit(20).all()

        return jsonify({
            "email": getattr(user, "email", None),
            "total_points": total_points,
            "points_breakdown": [{
                "points": p.points,
                "event": p.event,
                "timestamp": p.timestamp.isoformat() if p.timestamp else None,
                "awarded_by": p.awarded_by_officer
            } for p in points_records]
        }), 200
    finally:
        db.close()

@storefront_blueprint.route("/<string:org_prefix>/users/<string:user_email>/points", methods=["GET"])
@require_clerk_auth
@error_handler
def get_user_points_clerk(org_prefix, user_email):
    """Get user points using Clerk authentication"""
    db = next(db_connect.get_db())
    try:
        if request.clerk_user_email != user_email:
            return jsonify({"error": "Unauthorized: Email mismatch"}), 403
        
        from modules.organizations.models import Organization
        from modules.points.models import Points
        from modules.users.models import User
        
        organization = db.query(Organization).filter(Organization.prefix == org_prefix).first()
        if not organization:
            return jsonify({"error": "Organization not found"}), 404
        
        user = db.query(User).filter_by(email=user_email).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        total_points = db.query(func.sum(Points.points)).filter(
            Points.user_id == user.id,
            Points.organization_id == organization.id
        ).scalar() or 0
        
        points_records = db.query(Points).filter_by(
            user_id=user.id,
            organization_id=organization.id
        ).order_by(Points.timestamp.desc()).limit(20).all()
        
        return jsonify({
            "email": user.email,
            "total_points": total_points,
            "points_breakdown": [{
                "points": p.points,
                "event": p.event,
                "timestamp": p.timestamp.isoformat() if p.timestamp else None,
                "awarded_by": p.awarded_by_officer
            } for p in points_records]
        }), 200
    finally:
        db.close()
