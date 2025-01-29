export default class Slugify {
  constructor(config) {
    this.config = {
      inputSelector: '.govuk-input#name',
      outputSelector: '.govuk-input#reference',
      ...config
    }
    this.init()
  }

  slugify(input) {
    if (!input) return ''
    // make lower case and trim
    let slug = input.toLowerCase().trim()
    // remove accents from charaters
    slug = slug.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    // replace invalid chars with spaces
    slug = slug.replace(/[^a-z0-9\s-]/g, ' ').trim()
    // replace multiple spaces or hyphens with a single hyphen
    slug = slug.replace(/[\s-]+/g, '-')
    return slug
  }

  init() {
    const $input = document.querySelector(this.config.inputSelector)
    const $output = document.querySelector(this.config.outputSelector)

    if ($input != null && $output != null) {
      $input.addEventListener('keyup', () => {
        $output.value = this.slugify($input.value)
      })
    }
  }
}
