from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from utils.decorators import admin_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from cloudinary.uploader import upload, destroy
import json
from .models import Product, ProductVariant, VariantImage, Category, Author
from .forms import ProductForm, ProductVariantForm, VariantImageForm

ITEMS_PER_PAGE = 4

def get_form_context():
    categories = Category.objects.all()
    authors = Author.objects.filter(is_active=True)
    return {'categories': categories, 'authors': authors}

def handle_variant_image_uploads(request, variant, image_prefix):
    images = request.FILES.getlist(f'{image_prefix}-image')
    for index, image_file in enumerate(images):
        is_primary = request.POST.get(f'{image_prefix}-is_primary_{index}') == 'on'
        display_order = int(request.POST.get(f'{image_prefix}-display_order_{index}', 0))
        cropped_data = json.loads(request.POST.get(f'{image_prefix}-cropped_data_{index}', '{}'))
        
        try:
            upload_result = upload(
                image_file,
                crop='crop',
                width=cropped_data.get('width'),
                height=cropped_data.get('height'),
                x=cropped_data.get('x'),
                y=cropped_data.get('y')
            )
            VariantImage.objects.create(
                variant=variant,
                image=upload_result['public_id'],
                is_primary=is_primary,
                display_order=display_order
            )
        except Exception as e:
            messages.error(request, f"Image upload failed: {str(e)}")

def handle_variant_image_updates(request, variant, prefix):
    # Process image replacements
    for key in request.FILES:
        if key.startswith(f'{prefix}-replace_image_'):
            try:
                image_id = key.split('_')[-1]
                image = VariantImage.objects.get(image_id=image_id, variant=variant)
                
                # Get cropping data
                cropped_data = json.loads(request.POST.get(
                    f'{prefix}-replace_cropped_data_{image_id}', '{}'
                ))
                
                # Delete old image from Cloudinary
                destroy(image.image.public_id)
                
                # Upload new image with cropping
                new_image_file = request.FILES[key]
                upload_result = upload(
                    new_image_file,
                    crop='crop',
                    width=cropped_data.get('width'),
                    height=cropped_data.get('height'),
                    x=cropped_data.get('x'),
                    y=cropped_data.get('y')
                )
                
                # Update image record
                image.image = upload_result['public_id']
                image.save()
                
            except (VariantImage.DoesNotExist, Exception) as e:
                messages.error(request, f"Error replacing image: {str(e)}")

@admin_required
def admin_product_list(request):
    search_query = request.GET.get('search', '')
    if search_query:
        product_list = Product.objects.filter(
            Q(product_name__icontains=search_query) |
            Q(product_description__icontains=search_query),
            author__is_active=True
        ).order_by('-product_id')
    else:
        product_list = Product.objects.filter(author__is_active=True).order_by('-product_id')
    
    page = request.GET.get('page', 1)
    paginator = Paginator(product_list, ITEMS_PER_PAGE)
    
    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)
    
    context = {
        'products': products,
        'search_query': search_query,
    }
    return render(request, 'adminside/product/admin_product_list.html', context)

@admin_required
def admin_product_add(request):
    if request.method == 'POST':
        product_form = ProductForm(request.POST)
        variants_data = []
        variant_count = int(request.POST.get('variant_count', 0))        
        all_forms_valid = product_form.is_valid()

        for i in range(variant_count):
            prefix = f'variant_{i}'
            variant_form = ProductVariantForm(request.POST, prefix=prefix)
            variants_data.append((variant_form, prefix))
            all_forms_valid = all_forms_valid and variant_form.is_valid()

        if all_forms_valid:
            try:
                product = product_form.save()
                
                # Save variants and their images
                for variant_form, prefix in variants_data:
                    variant = variant_form.save(commit=False)
                    variant.product = product
                    variant.is_active = True  # Set default status as active
                    variant.save()
                    handle_variant_image_uploads(request, variant, prefix)

                messages.success(request, 'Product added successfully.')
                return redirect('products:admin_product_list')
            except Exception as e:
                messages.error(request, f'Error saving product: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        product_form = ProductForm()
        variants_data = [(ProductVariantForm(prefix='variant_0'), 'variant_0')]

    context = {
        'product_form': product_form,
        'variants_data': variants_data,
        **get_form_context()
    }
    return render(request, 'adminside/product/admin_product_add.html', context)

@admin_required
def admin_product_edit(request, product_id):
    product = get_object_or_404(Product, product_id=product_id)
    variants = product.variants.all()
    
    if request.method == 'POST':
        product_form = ProductForm(request.POST, instance=product)
        variants_data = []
        all_forms_valid = product_form.is_valid()
        
        # Validate variant forms
        for variant in variants:
            prefix = f'variant_{variant.id}'
            variant_form = ProductVariantForm(request.POST, prefix=prefix, instance=variant)
            variants_data.append((variant_form, prefix))
            all_forms_valid = all_forms_valid and variant_form.is_valid()
        
        if all_forms_valid:
            try:
                product = product_form.save()
                # Process each variant
                for variant_form, prefix in variants_data:
                    variant = variant_form.save(commit=False)
                    variant.product = product
                    variant.save()
                    
                    # Handle new image uploads
                    handle_variant_image_uploads(request, variant, prefix)
                    
                    # Handle image replacements
                    handle_variant_image_updates(request, variant, prefix)
                    
                    # Delete selected images
                    delete_images = request.POST.getlist(f'{prefix}-delete_images')
                    for image_id in delete_images:
                        try:
                            image = VariantImage.objects.get(image_id=image_id)
                            destroy(image.image.public_id)  # Delete from Cloudinary
                            image.delete()  # Delete from database
                        except VariantImage.DoesNotExist:
                            pass
                    
                    # Update primary image
                    primary_image_id = request.POST.get(f'{prefix}-primary_image')
                    if primary_image_id:
                        VariantImage.objects.filter(variant=variant).update(is_primary=False)
                        VariantImage.objects.filter(image_id=primary_image_id).update(is_primary=True)
                    
                    # Update display order
                    for image in variant.images.all():
                        display_order_key = f'{prefix}-display_order_{image.image_id}'
                        display_order = request.POST.get(display_order_key, image.display_order)
                        image.display_order = display_order
                        image.save()
                
                messages.success(request, 'Product updated successfully.')
                return redirect('products:admin_product_list')
            except Exception as e:
                messages.error(request, f'Error updating product: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        product_form = ProductForm(instance=product)
        variants_data = [
            (ProductVariantForm(instance=variant, prefix=f'variant_{variant.id}'), f'variant_{variant.id}')
            for variant in variants
        ]
    
    context = {
        'product_form': product_form,
        'variants_data': variants_data,
        'product': product,
        **get_form_context()
    }
    return render(request, 'adminside/product/admin_product_edit.html', context)

@admin_required
def admin_product_view(request, product_id):
    product = get_object_or_404(Product, product_id=product_id)
    return render(request, 'adminside/product/admin_product_view.html', {'product': product})

@admin_required
def admin_product_delete(request, product_id):
    product = get_object_or_404(Product, product_id=product_id)
    try:
        # Update all variants' status together
        variants = product.variants.all()
        new_status = not variants.first().is_active  # Toggle based on current status
        variants.update(is_active=new_status)
        
        action = "restored" if new_status else "deactivated"
        messages.success(request, f'Product: {product.product_name} has been {action}.')
    except Exception as e:
        messages.error(request, f'Error updating product status: {str(e)}')
    return redirect('products:admin_product_list')

@admin_required
def admin_orders_list(request):
    return render(request, 'adminside/orders/admin_order_list.html')

@admin_required
def admin_orders_view_details(request):
    return render(request, 'adminside/orders/admin_order_view_details.html')