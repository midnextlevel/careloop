from .create_dev_user import Command as CreateDevUserCommand


class Command(CreateDevUserCommand):
    help = 'Create a named fictional owner for local development login.'

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.set_defaults(role='owner', name='Test Parent')
