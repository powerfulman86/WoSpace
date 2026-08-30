# -*- coding: utf-8 -*-


def post_init_hook(env):
    """Initial sync for existing branch companies.

    Copy negative-stock product/category settings from parent company to its child branches.
    """
    Company = env["res.company"].sudo()
    ProductTemplate = env["product.template"].sudo()
    ProductCategory = env["product.category"].sudo()

    parent_companies = Company.search([("child_ids", "!=", False)])
    products = ProductTemplate.search([])
    categories = ProductCategory.search([])

    for parent_company in parent_companies:
        child_companies = Company.search([("parent_id", "=", parent_company.id)])

        for product in products:
            parent_value = product.with_company(parent_company).allow_negative_stock
            for child_company in child_companies:
                product.with_company(child_company).with_context(
                    skip_negative_stock_branch_sync=True
                ).write({"allow_negative_stock": parent_value})

        for category in categories:
            parent_value = category.with_company(parent_company).allow_negative_stock
            for child_company in child_companies:
                category.with_company(child_company).with_context(
                    skip_negative_stock_branch_sync=True
                ).write({"allow_negative_stock": parent_value})
