import axios from 'axios'

class GitHubServiceClass {
  async getStarsCount() {
    const { data } = await axios.get('https://api.github.com/repos/luml-ai/luml')
    return data.stargazers_count
  }
}

export const GitHubService = new GitHubServiceClass()
