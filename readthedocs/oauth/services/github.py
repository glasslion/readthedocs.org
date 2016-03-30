"""OAuth utility functions"""

import logging
import json
import re

from django.conf import settings
from requests.exceptions import RequestException
from allauth.socialaccount.models import SocialToken
from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter

from readthedocs.builds import utils as build_utils
from readthedocs.restapi.client import api

from ..models import RemoteOrganization, RemoteRepository
from .base import Service


DEFAULT_PRIVACY_LEVEL = getattr(settings, 'DEFAULT_PRIVACY_LEVEL', 'public')

log = logging.getLogger(__name__)


class GitHubService(Service):

    """Provider service for GitHub"""

    adapter = GitHubOAuth2Adapter
    # TODO replace this with a less naive check
    url_pattern = re.compile(r'github\.com')

    def sync(self):
        """Sync repositories and organizations"""
        self.sync_repositories()
        self.sync_organizations()

    def sync_repositories(self):
        """Sync repositories from GitHub API"""
        repos = self.paginate('https://api.github.com/user/repos?per_page=100')
        try:
            for repo in repos:
                self.create_repository(repo)
        except (TypeError, ValueError) as e:
            log.error('Error syncing GitHub repositories: %s',
                      str(e), exc_info=True)
            raise Exception('Could not sync your GitHub repositories, '
                            'try reconnecting your account')

    def sync_organizations(self):
        """Sync organizations from GitHub API"""
        try:
            orgs = self.paginate('https://api.github.com/user/orgs')
            for org in orgs:
                org_resp = self.get_session().get(org['url'])
                org_obj = self.create_organization(org_resp.json())
                # Add repos
                # TODO ?per_page=100
                org_repos = self.paginate(
                    '{org_url}/repos'.format(org_url=org['url'])
                )
                for repo in org_repos:
                    self.create_repository(repo, organization=org_obj)
        except (TypeError, ValueError) as e:
            log.error('Error syncing GitHub organizations: %s',
                      str(e), exc_info=True)
            raise Exception('Could not sync your GitHub organizations, '
                            'try reconnecting your account')

    def create_repository(self, fields, privacy=DEFAULT_PRIVACY_LEVEL,
                          organization=None):
        """Update or create a repository from GitHub API response

        :param fields: dictionary of response data from API
        :param privacy: privacy level to support
        :param organization: remote organization to associate with
        :type organization: RemoteOrganization
        :rtype: RemoteRepository
        """
        if (
                (privacy == 'private') or
                (fields['private'] is False and privacy == 'public')):
            try:
                repo = RemoteRepository.objects.get(
                    full_name=fields['full_name'],
                    users=self.user,
                    account=self.account,
                )
            except RemoteRepository.DoesNotExist:
                repo = RemoteRepository.objects.create(
                    full_name=fields['full_name'],
                    account=self.account,
                )
                repo.users.add(self.user)
            if repo.organization and repo.organization != organization:
                log.debug('Not importing %s because mismatched orgs' %
                          fields['name'])
                return None
            else:
                repo.organization = organization
            repo.name = fields['name']
            repo.description = fields['description']
            repo.ssh_url = fields['ssh_url']
            repo.html_url = fields['html_url']
            repo.private = fields['private']
            if repo.private:
                repo.clone_url = fields['ssh_url']
            else:
                repo.clone_url = fields['clone_url']
            repo.admin = fields.get('permissions', {}).get('admin', False)
            repo.vcs = 'git'
            repo.account = self.account
            repo.avatar_url = fields.get('owner', {}).get('avatar_url')
            repo.json = json.dumps(fields)
            repo.save()
            return repo
        else:
            log.debug('Not importing %s because mismatched type' %
                      fields['name'])

    def create_organization(self, fields):
        """Update or create remote organization from GitHub API response

        :param fields: dictionary response of data from API
        :rtype: RemoteOrganization
        """
        try:
            organization = RemoteOrganization.objects.get(
                slug=fields.get('login'),
                users=self.user,
                account=self.account,
            )
        except RemoteOrganization.DoesNotExist:
            organization = RemoteOrganization.objects.create(
                slug=fields.get('login'),
                account=self.account,
            )
            organization.users.add(self.user)
        organization.url = fields.get('html_url')
        organization.name = fields.get('name')
        organization.email = fields.get('email')
        organization.avatar_url = fields.get('avatar_url')
        organization.json = json.dumps(fields)
        organization.account = self.account
        organization.save()
        return organization

    def paginate(self, url):
        """Combines return from GitHub pagination

        :param url: start url to get the data from.

        See https://developer.github.com/v3/#pagination
        """
        resp = self.get_session().get(url)
        result = resp.json()
        next_url = resp.links.get('next', {}).get('url')
        if next_url:
            result.extend(self.paginate(next_url))
        return result

    def setup_webhook(self, project):
        """Set up GitHub project webhook for project

        :param project: project to set up webhook for
        :type project: Project
        :returns: boolean based on webhook set up success
        :rtype: bool
        """
        session = self.get_session()
        owner, repo = build_utils.get_github_username_repo(url=project.repo)
        data = json.dumps({
            'name': 'readthedocs',
            'active': True,
            'config': {'url': 'https://{domain}/github'.format(domain=settings.PRODUCTION_DOMAIN)}
        })
        resp = None
        try:
            resp = session.post(
                ('https://api.github.com/repos/{owner}/{repo}/hooks'
                 .format(owner=owner, repo=repo)),
                data=data,
                headers={'content-type': 'application/json'}
            )
            if resp.status_code == 201:
                log.info('GitHub webhook creation successful for project: %s',
                         project)
                return True
        except RequestException:
            log.error('GitHub webhook creation failed for project: %s',
                      project, exc_info=True)
            pass
        else:
            log.error('GitHub webhook creation failed for project: %s',
                      project)
            return False

    @classmethod
    def get_token_for_project(cls, project, force_local=False):
        """Get access token for project by iterating over project users"""
        # TODO why does this only target GitHub?
        if not getattr(settings, 'ALLOW_PRIVATE_REPOS', False):
            return None
        token = None
        try:
            if getattr(settings, 'DONT_HIT_DB', True) and not force_local:
                token = api.project(project.pk).token().get()['token']
            else:
                for user in project.users.all():
                    tokens = SocialToken.objects.filter(
                        account__user=user,
                        app__provider=cls.adapter.provider_id)
                    if tokens.exists():
                        token = tokens[0].token
        except Exception:
            log.error('Failed to get token for user', exc_info=True)
        return token
