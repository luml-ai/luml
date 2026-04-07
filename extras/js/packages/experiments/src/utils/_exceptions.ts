export class LumlExperimentsError extends Error {
  constructor(message = 'Luml Experiments error') {
    super(message);
    this.name = 'LumlExperimentsError';
  }
}

export class LumlFilterError extends LumlExperimentsError {
  constructor(message = 'Invalid filter string') {
    super(message);
    this.name = 'LumlFilterError';
  }
}