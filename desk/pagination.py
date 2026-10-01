from rest_framework.pagination import PageNumberPagination


class DeskPagination(PageNumberPagination):
    page_size = 50
