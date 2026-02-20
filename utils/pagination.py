from rest_framework.pagination import PageNumberPagination




class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10

    page_size_query_param = 'page_size'
    max_page_size = 100

# ✅ Pagination - 6 per page
class BlogPagination(PageNumberPagination):


    page_size = 10

    page_size_query_param = 'page_size'  # optional if you want users to set page_size
    max_page_size = 100
