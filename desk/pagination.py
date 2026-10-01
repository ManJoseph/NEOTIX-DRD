from rest_framework.pagination import PageNumberPagination


class RequestPagination(PageNumberPagination):
    page_size = 50
